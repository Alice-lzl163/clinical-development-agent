import json
import platform
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageContractError, PackageExecutionError, RequestValidationError, RuntimeDependencyError
from sample_size.engines.r_engine import RExecutionEngine
from sample_size.validation.compare_platform_evidence import compare
from sample_size.validation.dependency_compatibility import classify_runtime


ROOT = Path(__file__).resolve().parents[1]


class StubEngine:
    def __init__(self, result): self.result = result
    def execute(self, **_): return dict(self.result)


def t_parameters(**changes):
    value = {"standardized_effect": .5, "alpha": .05, "power": .8, "dropout_rate": 0, "alternative": "two_sided"}
    value.update(changes)
    return value


def valid_raw(**changes):
    value = {"package_n": 33.4, "analysis_n": 34, "achieved_power": .8078, "package_version": "1.3.0", "r_version": "R version 4.6.1 (test)", "session_info": "test", "warnings": []}
    value.update(changes)
    return value


class ProductionQualificationTests(unittest.TestCase):
    def test_ci_numerical_entry_point_resolves_package_from_checkout_root(self):
        environment = dict(__import__("os").environ)
        environment.pop("PYTHONPATH", None)
        process = subprocess.run(
            [sys.executable, "-m", "sample_size.validation.run_numerical_validation", "--help"],
            cwd=ROOT, env=environment, text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertIn("--evidence-output", process.stdout)

    def test_machine_readable_assessment_has_six_unpromoted_methods(self):
        data = yaml.safe_load((ROOT / "sample_size/validation/production_qualification.yaml").read_text(encoding="utf-8"))
        self.assertEqual(6, len(data["method_assessment"]))
        self.assertEqual({"ttest_one", "ttest_paired", "ttest_ind", "anova", "proportion_two", "be_tost"}, {m["test_key"] for m in data["method_assessment"]})
        self.assertTrue(all(m["benchmark_validated"] and not m["production_candidate"] for m in data["method_assessment"]))

    def test_dependency_and_os_registries_are_evidence_bounded(self):
        dependencies = yaml.safe_load((ROOT / "sample_size/validation/dependency_compatibility.yaml").read_text(encoding="utf-8"))
        self.assertEqual({"pwr", "TrialSize", "PowerTOST", "jsonlite"}, {item["dependency"] for item in dependencies["qualifications"]})
        self.assertEqual([], dependencies["incompatible_versions"])
        self.assertTrue(all(item["qualification_status"] == "MATCHED_VALIDATED_ENVIRONMENT" for item in dependencies["qualifications"]))
        self.assertEqual("UNVALIDATED_VERSION", classify_runtime("pwr", "9.9.9", "R version 4.6.1", operating_system="Windows", architecture="AMD64"))
        os_data = yaml.safe_load((ROOT / "sample_size/validation/os_qualification.yaml").read_text(encoding="utf-8"))
        states = {item["operating_system"]: item["qualification_status"] for item in os_data["platforms"]}
        self.assertEqual({"Windows": "QUALIFIED", "Linux": "UNQUALIFIED", "macOS": "UNQUALIFIED"}, states)
        self.assertEqual("PENDING", os_data["cross_platform_comparison"]["status"])

    def test_cross_platform_comparator_accepts_identical_evidence(self):
        evidence = ROOT / "sample_size/validation/round42_evidence.json"
        result = compare([evidence, evidence])
        self.assertEqual("PASS", result["status"])
        self.assertEqual(24, result["fixture_count"])

    def test_input_contract_fails_closed(self):
        invalid = [
            {}, t_parameters(extra=1), t_parameters(alpha=0), t_parameters(power=1),
            t_parameters(standardized_effect=0), t_parameters(dropout_rate=1),
            t_parameters(alternative="up"),
        ]
        for parameters in invalid:
            with self.subTest(parameters=parameters), self.assertRaises(RequestValidationError):
                calculate_sample_size({"test_key": "ttest_one", "parameters": parameters}, engine=StubEngine(valid_raw()))
        with self.assertRaises(RequestValidationError):
            calculate_sample_size({"test_key": "ttest_ind", "parameters": {**t_parameters(), "allocation_ratio": 2}}, engine=StubEngine(valid_raw()))
        with self.assertRaises(RequestValidationError):
            calculate_sample_size({"test_key": "ttest_one", "solve_mode": "power", "parameters": t_parameters()}, engine=StubEngine(valid_raw()))

    def test_missing_runtime_and_package_fail_closed(self):
        with patch("sample_size.engines.r_engine.shutil.which", return_value=None) as discovery:
            engine = RExecutionEngine(rscript=None)
            self.assertFalse(engine.available)
            with self.assertRaises(RuntimeDependencyError):
                engine.execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")
            discovery.assert_called_once_with("Rscript")
        failed = type("P", (), {"returncode": 1, "stdout": "", "stderr": "Error: DEPENDENCY_MISSING: pwr"})()
        with patch("sample_size.engines.r_engine.subprocess.run", return_value=failed) as runner, self.assertRaises(RuntimeDependencyError):
            RExecutionEngine(rscript="Rscript").execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")
        self.assertIn('requireNamespace("pwr"', runner.call_args.kwargs["input"])

    def test_runtime_discovery_result_is_preserved_when_not_injected(self):
        discovered = str(ROOT / "test-runtime" / "Rscript")
        with patch("sample_size.engines.r_engine.shutil.which", return_value=discovered) as discovery:
            engine = RExecutionEngine()
        discovery.assert_called_once_with("Rscript")
        self.assertTrue(engine.available)
        self.assertEqual(discovered, engine.rscript)

    def test_malformed_failure_timeout_and_nonfinite_fail_closed(self):
        cases = [
            (type("P", (), {"returncode": 0, "stdout": "no marker", "stderr": ""})(), PackageExecutionError),
            (type("P", (), {"returncode": 0, "stdout": "__CDA_SAMPLE_SIZE_JSON__not-json", "stderr": ""})(), PackageExecutionError),
            (type("P", (), {"returncode": 2, "stdout": "", "stderr": "boom"})(), PackageExecutionError),
            (type("P", (), {"returncode": 0, "stdout": "__CDA_SAMPLE_SIZE_JSON__{\"x\":NaN}", "stderr": ""})(), PackageExecutionError),
        ]
        for process, error in cases:
            with self.subTest(stdout=process.stdout), patch("sample_size.engines.r_engine.subprocess.run", return_value=process), self.assertRaises(error):
                RExecutionEngine(rscript="Rscript").execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")
        with patch("sample_size.engines.r_engine.subprocess.run", side_effect=subprocess.TimeoutExpired("Rscript", 1)), self.assertRaises(PackageExecutionError):
            RExecutionEngine(rscript="Rscript", timeout_seconds=1).execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")

    def test_invalid_n_and_power_fail_closed(self):
        for raw in (valid_raw(analysis_n=0), valid_raw(achieved_power=float("inf")), valid_raw(achieved_power=-.1)):
            with self.subTest(raw=raw), self.assertRaises((PackageExecutionError, ValueError, OverflowError)):
                calculate_sample_size({"test_key": "ttest_one", "parameters": t_parameters()}, engine=StubEngine(raw))

    def test_version_match_and_mismatch_reporting(self):
        matched = calculate_sample_size({"test_key": "ttest_one", "parameters": t_parameters()}, engine=StubEngine(valid_raw()))
        expected = "MATCHED_VALIDATED_ENVIRONMENT" if platform.system() == "Windows" and platform.machine().lower() == "amd64" else "UNVALIDATED_VERSION"
        self.assertEqual(expected, matched.validation_environment)
        self.assertEqual("BENCHMARK_VALIDATED" if expected.startswith("MATCHED") else "IMPLEMENTED_UNVALIDATED", matched.validation_status)
        mismatch = calculate_sample_size({"test_key": "ttest_one", "parameters": t_parameters()}, engine=StubEngine(valid_raw(package_version="1.3.1")))
        self.assertEqual("UNVALIDATED_VERSION", mismatch.validation_environment)
        self.assertEqual("IMPLEMENTED_UNVALIDATED", mismatch.validation_status)
        self.assertTrue(any("differ" in warning for warning in mismatch.warnings))

    def test_tested_compatible_and_incompatible_states_are_explicit(self):
        request = {"test_key": "ttest_one", "parameters": t_parameters()}
        with patch("sample_size.methods.fixed_designs.classify_runtime", return_value="TESTED_COMPATIBLE_VERSION"):
            result = calculate_sample_size(request, engine=StubEngine(valid_raw(package_version="1.2.9")))
        self.assertEqual("TESTED_COMPATIBLE_VERSION", result.validation_environment)
        self.assertEqual("BENCHMARK_VALIDATED", result.validation_status)
        with patch("sample_size.methods.fixed_designs.classify_runtime", return_value="INCOMPATIBLE_VERSION"), self.assertRaises(PackageExecutionError):
            calculate_sample_size(request, engine=StubEngine(valid_raw(package_version="0.0.0")))

    def test_protocol_ready_output_contract(self):
        result = calculate_sample_size({"test_key": "ttest_one", "parameters": t_parameters()}, engine=StubEngine(valid_raw()))
        protocol = result.to_protocol_dict()
        self.assertEqual({"statistical_result", "operational_adjustment", "method_metadata", "validation_metadata", "interpretation", "reproducibility"}, set(protocol))
        self.assertEqual(34, protocol["statistical_result"]["total_analyzable_n"])
        self.assertEqual("fixed-design-round4-v1", protocol["validation_metadata"]["benchmark_id"])
        self.assertTrue(protocol["method_metadata"]["statistical_specification_version"].startswith("sha256:"))
        self.assertEqual({"one_sample": 34}, protocol["operational_adjustment"]["randomized_group_sizes"])
        self.assertIn("pwr::pwr.t.test", protocol["reproducibility"]["exact_r_code"])

    def test_no_fallback_routes_exist(self):
        engine_source = (ROOT / "sample_size/engines/r_engine.py").read_text(encoding="utf-8").lower()
        router_source = (ROOT / "sample_size/agent/router.py").read_text(encoding="utf-8").lower()
        forbidden = ("scipy", "http://", "https://", "coze", "llm")
        for token in forbidden:
            self.assertNotIn(token, engine_source)
            self.assertNotIn(token, router_source)


if __name__ == "__main__": unittest.main()
