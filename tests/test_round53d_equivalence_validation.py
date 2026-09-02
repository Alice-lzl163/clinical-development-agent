import json
import math
import unittest
from pathlib import Path

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageExecutionError, RequestValidationError, RuntimeDependencyError

ROOT = Path(__file__).resolve().parents[1]


class RecordingEngine:
    def __init__(self, raw): self.raw, self.calls = raw, []
    def execute(self, **kwargs): self.calls.append(kwargs); return dict(self.raw)


def raw(**updates):
    value = {"analysis_n_treatment": 124, "analysis_n_control": 62, "achieved_power": .806,
        "has_preceding_candidate": True, "preceding_power": .799, "search_iterations": 61,
        "authoritative_package_calls": 61, "package_version": "1.5.7",
        "r_version": "R version 4.6.1 (test)", "session_info": "test", "warnings": []}
    value.update(updates); return value


class EquivalenceImplementationTests(unittest.TestCase):
    base = {"expected_difference": .1, "sd": 1, "equivalence_margin": .5,
            "allocation_ratio": 2, "alpha": .05, "power": .8, "dropout_rate": .1}

    def test_exact_mapping_minimality_dropout_and_metadata(self):
        result = calculate_sample_size({"test_key":"equivalence", "parameters":self.base}, engine=RecordingEngine(raw()))
        self.assertEqual("PowerTOST::power.TOST", result.function)
        self.assertEqual({"alpha":.05,"logscale":False,"theta0":.1,"theta1":-.5,"theta2":.5,"CV":1,
            "n":[124,62],"design":"parallel","method":"exact","robust":False}, result.package_arguments)
        self.assertEqual({"treatment":124,"control":62}, result.sample_size_per_group)
        self.assertEqual(math.ceil(124/.9)+math.ceil(62/.9), result.randomized_sample_size)
        self.assertEqual("round-5.3d", result.implementation_version)
        self.assertEqual("round5-equivalence-powertost-v1", result.benchmark_id)
        self.assertEqual("BENCHMARK_VALIDATED", result.validation_status)
        self.assertTrue(result.derived_parameters["minimal_control_arm_under_declared_search"])
        self.assertNotIn("TwoSampleMean.Equivalence", result.reproducible_code)

    def test_fail_closed_dependency_and_search_boundaries(self):
        class Missing:
            def execute(self, **kwargs): raise RuntimeDependencyError("missing PowerTOST")
        with self.assertRaises(RuntimeDependencyError):
            calculate_sample_size({"test_key":"equivalence","parameters":self.base}, engine=Missing())
        with self.assertRaises(PackageExecutionError):
            calculate_sample_size({"test_key":"equivalence","parameters":self.base}, engine=RecordingEngine(raw(preceding_power=.801)))
        class Exhausted:
            def execute(self, **kwargs): raise PackageExecutionError("SEARCH_CONVERGENCE_FAILURE: no candidate achieved target power")
        with self.assertRaisesRegex(PackageExecutionError, "SEARCH_CONVERGENCE_FAILURE"):
            calculate_sample_size({"test_key":"equivalence","parameters":self.base}, engine=Exhausted())
        power = {"expected_difference":.1,"sd":1,"equivalence_margin":.5,"alpha":.05,"analyzable_treatment":1000001,"analyzable_control":2}
        with self.assertRaises(RequestValidationError):
            calculate_sample_size({"test_key":"equivalence","solve_mode":"power","parameters":power}, engine=RecordingEngine(raw()))


class EquivalenceFrozenEvidenceTests(unittest.TestCase):
    def test_new_benchmark_is_frozen_and_all_gates_pass(self):
        evidence = json.loads((ROOT/"sample_size/validation/round5_equivalence_powertost_evidence.json").read_text(encoding="utf-8"))
        fixtures = yaml.safe_load((ROOT/"sample_size/validation/benchmarks/round5_equivalence_powertost.yaml").read_text(encoding="utf-8"))
        self.assertEqual("round5-equivalence-powertost-v1", evidence["benchmark_id"])
        self.assertEqual("FROZEN_VALIDATED", evidence["benchmark_status"])
        self.assertEqual(6, len(evidence["fixtures"]))
        self.assertTrue(all(row["status"] == "PASS" for row in evidence["fixtures"].values()))
        self.assertTrue(all(value == "PASS" for value in evidence["validation_gates"].values()))
        self.assertEqual("FROZEN_VALIDATED", fixtures["status"])
        self.assertEqual(3, len(evidence["simulations"]))
        self.assertTrue(all(row["status"] == "PASS" for row in evidence["simulations"].values()))
        self.assertEqual("1.5.7", evidence["environment"]["PowerTOST"]["version"])

    def test_historical_failed_evidence_remains_separate(self):
        historical = json.loads((ROOT/"sample_size/validation/round5_fixed_design_evidence.json").read_text(encoding="utf-8"))
        self.assertEqual("STATISTICAL_CONTRACT_DEFECT", historical["method_gates"]["equivalence"]["blocker"])
        self.assertEqual("FAIL", historical["fixtures"]["eq_k2"]["status"])
        self.assertEqual("FAIL", historical["fixtures"]["eq_khalf"]["status"])


if __name__ == "__main__": unittest.main()
