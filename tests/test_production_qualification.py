import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageContractError, PackageExecutionError, RequestValidationError, RuntimeDependencyError
from sample_size.engines.r_engine import RExecutionEngine


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
    def test_machine_readable_assessment_has_six_unpromoted_methods(self):
        data = yaml.safe_load((ROOT / "sample_size/validation/production_qualification.yaml").read_text(encoding="utf-8"))
        self.assertEqual(6, len(data["method_assessment"]))
        self.assertEqual({"ttest_one", "ttest_paired", "ttest_ind", "anova", "proportion_two", "be_tost"}, {m["test_key"] for m in data["method_assessment"]})
        self.assertTrue(all(m["benchmark_validated"] and not m["production_candidate"] for m in data["method_assessment"]))

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
        with self.assertRaises(RuntimeDependencyError):
            RExecutionEngine(rscript=None).execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")
        failed = type("P", (), {"returncode": 1, "stdout": "", "stderr": "Error: DEPENDENCY_MISSING: pwr"})()
        with patch("sample_size.engines.r_engine.subprocess.run", return_value=failed), self.assertRaises(RuntimeDependencyError):
            RExecutionEngine(rscript="Rscript").execute(package="pwr", function="pwr::pwr.t.test", calculation_code="list()")

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
        self.assertEqual("MATCHED_VALIDATED_ENVIRONMENT", matched.validation_environment)
        self.assertEqual("BENCHMARK_VALIDATED", matched.validation_status)
        mismatch = calculate_sample_size({"test_key": "ttest_one", "parameters": t_parameters()}, engine=StubEngine(valid_raw(package_version="1.3.1")))
        self.assertEqual("UNVALIDATED_VERSION", mismatch.validation_environment)
        self.assertEqual("IMPLEMENTED_UNVALIDATED", mismatch.validation_status)
        self.assertTrue(any("differ" in warning for warning in mismatch.warnings))

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
