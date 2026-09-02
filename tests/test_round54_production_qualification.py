import json
import tempfile
import unittest
from pathlib import Path

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageExecutionError, RuntimeDependencyError
from sample_size.validation.compare_platform_evidence import compare
from sample_size.validation.dependency_compatibility import classify_runtime

ROOT = Path(__file__).resolve().parents[1]
METHODS = {"proportion_one", "proportion_paired", "equivalence", "non_inferiority", "superiority_margin", "odds_ratio", "risk_ratio"}


class Round54ProductionQualificationTests(unittest.TestCase):
    def test_gate_matrix_is_fail_closed_pending_hosted_evidence(self):
        data = yaml.safe_load((ROOT/"sample_size/validation/production_qualification.yaml").read_text(encoding="utf-8"))
        rows = data["round5_method_assessment"]
        self.assertEqual(METHODS, {row["test_key"] for row in rows})
        for row in rows:
            self.assertEqual("SPEC_FROZEN", row["statistical_specification"])
            self.assertEqual("IMPLEMENTED", row["implementation"])
            self.assertEqual("BENCHMARK_VALIDATED", row["numerical_validation"])
            self.assertEqual("PENDING", row["gate_matrix"]["H_runtime_os"])
            self.assertFalse(row["production_candidate"])
            self.assertFalse(row["production"])
            self.assertTrue(row["remaining_gaps"])

    def test_local_live_evidence_covers_protocol_contract_for_all_methods(self):
        evidence = json.loads((ROOT/"sample_size/validation/round54_local_qualification.json").read_text(encoding="utf-8"))
        self.assertEqual("PASS", evidence["status"])
        self.assertEqual(25, len(evidence["fixtures"]))
        self.assertEqual(50, evidence["live_execution"]["successful"])
        represented = {row["agent_result"]["test_key"] for row in evidence["fixtures"].values()}
        self.assertEqual(METHODS, represented)
        required = {"test_key","method_id","solve_mode","analysis_required_sample_size","randomized_sample_size","achieved_power","alpha","sidedness","allocation","assumptions","unsupported_domains","warnings","package","package_version","function","specification_version","implementation_version","benchmark_id","validation_status","reproducible_code"}
        for row in evidence["fixtures"].values():
            self.assertTrue(required <= set(row["agent_result"])); self.assertEqual("PASS", row["status"])
            self.assertTrue(row["agent_result"]["unsupported_domains"])

    def test_dependency_scoping_and_unknown_versions(self):
        registry = yaml.safe_load((ROOT/"sample_size/validation/dependency_compatibility.yaml").read_text(encoding="utf-8"))
        gs = [x for x in registry["qualifications"] if x["dependency"] == "gsDesign"]
        self.assertEqual({"odds_ratio","risk_ratio"}, set(gs[0]["tested_methods"]))
        power = [x for x in registry["qualifications"] if x["dependency"] == "PowerTOST"]
        self.assertEqual({"be_tost","equivalence"}, set().union(*(set(x["tested_methods"]) for x in power)))
        for package in ("pwr","TrialSize","PowerTOST","gsDesign"):
            self.assertEqual("UNVALIDATED_VERSION", classify_runtime(package, "999.0", "R version 4.6.1", operating_system="Windows", architecture="AMD64"))

    def test_all_methods_propagate_dependency_and_execution_failures_without_fallback(self):
        requests = {
            "proportion_one": {"null_probability":.3,"alternative_probability":.45,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"greater"},
            "proportion_paired": {"p_treatment_only":.2,"p_control_only":.5,"alpha":.05,"power":.8,"dropout_rate":0},
            "equivalence": {"expected_difference":.1,"sd":1,"equivalence_margin":.5,"allocation_ratio":1,"alpha":.05,"power":.8,"dropout_rate":0},
            "non_inferiority": {"control_probability":.6,"treatment_probability":.62,"noninferiority_margin":.1,"allocation_ratio":1,"alpha":.025,"power":.8,"dropout_rate":0},
            "superiority_margin": {"control_probability":.4,"treatment_probability":.55,"superiority_margin":.05,"allocation_ratio":1,"alpha":.025,"power":.8,"dropout_rate":0},
            "odds_ratio": {"control_probability":.2,"alternative_odds_ratio":2,"null_odds_ratio":1,"allocation_ratio":1,"alpha":.025,"power":.8,"dropout_rate":0},
            "risk_ratio": {"control_probability":.2,"alternative_risk_ratio":1.8,"null_risk_ratio":1,"allocation_ratio":1,"alpha":.025,"power":.8,"dropout_rate":0},
        }
        class FailingEngine:
            def __init__(self,error): self.error=error
            def execute(self,**kwargs): raise self.error
        for method, parameters in requests.items():
            for error in (RuntimeDependencyError("missing runtime/package"), PackageExecutionError("malformed/missing/nonfinite/timeout/subprocess failure")):
                with self.subTest(method=method, error=type(error).__name__), self.assertRaises(type(error)):
                    calculate_sample_size({"test_key":method,"parameters":parameters},engine=FailingEngine(error))
        for path in (ROOT/"sample_size/engines/r_engine.py", ROOT/"sample_size/agent/router.py"):
            source = path.read_text(encoding="utf-8").lower()
            for token in ("scipy", "http://", "https://", "coze", "llm"): self.assertNotIn(token, source)

    def test_round5_cross_platform_comparator_supports_two_benchmarks_and_fails_closed(self):
        source = json.loads((ROOT/"sample_size/validation/round54_local_qualification.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            paths=[]
            for name in ("windows-latest","ubuntu-latest","macos-latest"):
                path=Path(directory)/f"sample-size-runtime-{name}"/"round5-evidence.json"; path.parent.mkdir(); path.write_text(json.dumps(source)); paths.append(path)
            result=compare(paths, expected_platforms=["windows-latest","ubuntu-latest","macos-latest"])
            self.assertEqual("PASS",result["status"]); self.assertEqual(25,result["fixture_count"])
            self.assertEqual(["round5-equivalence-powertost-v1","round5-fixed-design-v1"],result["benchmark_ids"])
            changed=json.loads(json.dumps(source)); first=next(iter(changed["fixtures"].values())); first["agent_result"]["derived_parameters"]["randomized_total"] = 999999
            paths[1].write_text(json.dumps(changed))
            self.assertEqual("FAIL",compare(paths, expected_platforms=["windows-latest","ubuntu-latest","macos-latest"])["status"])

    def test_workflow_installs_exact_round5_dependencies_and_runs_all_stages(self):
        workflow=(ROOT/".github/workflows/sample-size-runtime-qualification.yml").read_text(encoding="utf-8")
        for text in ('install_r_dependencies.R','--verify-only','run_round5_hosted_qualification','tests.test_round54_production_qualification','round5-evidence.json','round5-cross-platform-comparison.json'):
            self.assertIn(text,workflow)
        self.assertNotIn('install.packages("gsDesign")',workflow)

    def test_r_bootstrap_matches_exact_dependency_manifest(self):
        manifest=yaml.safe_load((ROOT/"sample_size/r_dependencies.yaml").read_text(encoding="utf-8"))
        expected={name:str(row["validated_version"]) for name,row in {**manifest["helper_packages"],**manifest["statistical_packages"]}.items()}
        script=(ROOT/"sample_size/validation/install_r_dependencies.R").read_text(encoding="utf-8")
        self.assertEqual({"jsonlite":"2.0.0","pwr":"1.3.0","TrialSize":"1.4.1","PowerTOST":"1.5.7","gsDesign":"3.11.0"},expected)
        for package,version in expected.items(): self.assertIn(f'{package} = "{version}"',script)
        self.assertIn("DEPENDENCY_VERSION_MISMATCH",script)
        self.assertIn("DEPENDENCY_MISSING",script)


if __name__ == "__main__": unittest.main()
