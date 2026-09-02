import math
import unittest

from sample_size import calculate_sample_size
from sample_size.engines.errors import RequestValidationError, RuntimeDependencyError, UnsupportedSolveModeError
from sample_size.registry.method_registry import IMPLEMENTED_KEYS


class RecordingEngine:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return dict(self.raw)


def raw(**changes):
    result = {
        "analysis_n": 20,
        "analysis_n_treatment": 30,
        "analysis_n_control": 20,
        "achieved_power": 0.81,
        "package_version": "1.3.0",
        "r_version": "R version 4.6.1 (test)",
        "session_info": "test",
        "warnings": [],
    }
    result.update(changes)
    return result


class Round52CalculatorTests(unittest.TestCase):
    def test_registry_includes_the_frozen_round5_methods(self):
        self.assertTrue({"proportion_one", "proportion_paired", "equivalence", "non_inferiority", "superiority_margin"}.issubset(IMPLEMENTED_KEYS))
        self.assertTrue({"odds_ratio", "risk_ratio"}.issubset(IMPLEMENTED_KEYS))

    def test_one_sample_proportion_mapping_modes_and_dropout(self):
        engine = RecordingEngine(raw())
        parameters = {"null_probability": .2, "alternative_probability": .35, "alpha": .05, "power": .8, "dropout_rate": .1, "alternative": "greater"}
        result = calculate_sample_size({"test_key": "proportion_one", "parameters": parameters}, engine=engine)
        self.assertEqual(20, result.analysis_required_sample_size)
        self.assertEqual(math.ceil(20 / .9), result.randomized_sample_size)
        self.assertGreater(result.derived_parameters["signed_cohen_h"], 0)
        self.assertEqual("pwr::pwr.p.test", result.function)
        self.assertEqual("BENCHMARK_VALIDATED", result.validation_status)
        self.assertEqual("round-5.2a", result.implementation_version)
        self.assertEqual("round5-fixed-design-v1", result.benchmark_id)
        self.assertFalse(any("not completed numerical benchmark validation" in warning for warning in result.warnings))
        self.assertIn("forward <- pwr::pwr.p.test", result.reproducible_code)

        power_engine = RecordingEngine(raw(achieved_power=.73))
        power_parameters = {"null_probability": .2, "alternative_probability": .1, "alpha": .05, "alternative": "less", "analyzable_sample_size": 40}
        powered = calculate_sample_size({"test_key": "proportion_one", "solve_mode": "power", "parameters": power_parameters}, engine=power_engine)
        self.assertEqual(40, powered.analysis_required_sample_size)
        self.assertIsNone(powered.randomized_sample_size)
        self.assertLess(powered.derived_parameters["signed_cohen_h"], 0)
        self.assertEqual("less", powered.package_arguments["alternative"])

    def test_one_sample_direction_and_equal_probability_fail_closed(self):
        base = {"null_probability": .2, "alternative_probability": .1, "alpha": .05, "power": .8, "dropout_rate": 0, "alternative": "greater"}
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key": "proportion_one", "parameters": base}, engine=RecordingEngine(raw()))
        base.update(alternative_probability=.2, alternative="two_sided")
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key": "proportion_one", "parameters": base}, engine=RecordingEngine(raw()))

    def test_mcnemar_mapping_pairs_dropout_and_invalid_domains(self):
        engine = RecordingEngine(raw(package_version="1.4.1", analysis_n=59))
        parameters = {"p_treatment_only": .2, "p_control_only": .5, "alpha": .05, "power": .8, "dropout_rate": .1}
        result = calculate_sample_size({"test_key": "proportion_paired", "parameters": parameters}, engine=engine)
        self.assertAlmostEqual(.2, result.package_arguments["beta"])
        self.assertEqual({"alpha": .05, "psai": .4, "paid": .7}, {key: result.package_arguments[key] for key in ("alpha", "psai", "paid")})
        self.assertEqual({"complete_matched_pairs": 59}, result.sample_size_per_sequence)
        self.assertEqual(math.ceil(59 / .9), result.randomized_sample_size)
        self.assertEqual("two_sided", result.sidedness)
        self.assertIn("TrialSize::McNemar.Test", result.reproducible_code)
        self.assertEqual("BENCHMARK_VALIDATED", result.validation_status)
        with self.assertRaises(UnsupportedSolveModeError):
            calculate_sample_size({"test_key": "proportion_paired", "solve_mode": "power", "parameters": parameters}, engine=engine)
        for changes in ({"p_treatment_only": 0}, {"p_treatment_only": .6}, {"p_treatment_only": .5}):
            invalid = dict(parameters); invalid.update(changes)
            with self.subTest(changes=changes), self.assertRaises(RequestValidationError):
                calculate_sample_size({"test_key": "proportion_paired", "parameters": invalid}, engine=engine)

    def test_equivalence_mapping_allocation_dropout_and_boundary(self):
        engine = RecordingEngine(raw(package_version="1.4.1", analysis_n_treatment=45, analysis_n_control=30))
        parameters = {"expected_difference": .1, "sd": 1.2, "equivalence_margin": .3, "allocation_ratio": 1.5, "alpha": .05, "power": .8, "dropout_rate": .1}
        result = calculate_sample_size({"test_key": "equivalence", "parameters": parameters}, engine=engine)
        self.assertAlmostEqual(.2, result.package_arguments["beta"])
        self.assertEqual({"alpha": .05, "sigma": 1.2, "k": 1.5, "delta": .3, "margin": .1}, {key: result.package_arguments[key] for key in ("alpha", "sigma", "k", "delta", "margin")})
        self.assertEqual({"treatment": 45, "control": 30}, result.sample_size_per_group)
        self.assertEqual(75, result.analysis_required_sample_size)
        self.assertEqual(math.ceil(45/.9) + math.ceil(30/.9), result.randomized_sample_size)
        self.assertEqual("IMPLEMENTED_UNVALIDATED", result.validation_status)
        invalid = dict(parameters, expected_difference=.3)
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key": "equivalence", "parameters": invalid}, engine=engine)

    def test_ni_and_superiority_use_distinct_package_margins(self):
        base = {"control_probability": .5, "treatment_probability": .6, "allocation_ratio": 1.5, "alpha": .025, "power": .8, "dropout_rate": .1}
        for key, field, margin, expected in (("non_inferiority", "noninferiority_margin", .1, -.1), ("superiority_margin", "superiority_margin", .05, .05)):
            with self.subTest(key=key):
                engine = RecordingEngine(raw(package_version="1.4.1", analysis_n_treatment=60, analysis_n_control=40))
                result = calculate_sample_size({"test_key": key, "parameters": {**base, field: margin}}, engine=engine)
                self.assertEqual("TrialSize::TwoSampleProportion.NIS", result.function)
                self.assertAlmostEqual(.1, result.package_arguments["delta"])
                self.assertEqual(expected, result.package_arguments["margin"])
                self.assertEqual(expected, result.derived_parameters["package_margin"])
                self.assertEqual({"treatment": 60, "control": 40}, result.sample_size_per_group)
                self.assertEqual("BENCHMARK_VALIDATED", result.validation_status)

    def test_margin_domains_fail_closed(self):
        ni = {"control_probability": .5, "treatment_probability": .39, "noninferiority_margin": .1, "allocation_ratio": 1, "alpha": .025, "power": .8, "dropout_rate": 0}
        sup = {"control_probability": .5, "treatment_probability": .54, "superiority_margin": .05, "allocation_ratio": 1, "alpha": .025, "power": .8, "dropout_rate": 0}
        for key, parameters in (("non_inferiority", ni), ("superiority_margin", sup)):
            with self.subTest(key=key), self.assertRaises(RequestValidationError):
                calculate_sample_size({"test_key": key, "parameters": parameters}, engine=RecordingEngine(raw(package_version="1.4.1")))
        ni["noninferiority_margin"] = 0
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key": "non_inferiority", "parameters": ni}, engine=RecordingEngine(raw(package_version="1.4.1")))

    def test_new_adapters_propagate_runtime_dependency_failure(self):
        class MissingRuntime:
            def execute(self, **_): raise RuntimeDependencyError("Rscript unavailable")
        parameters = {"p_treatment_only": .2, "p_control_only": .5, "alpha": .05, "power": .8, "dropout_rate": 0}
        with self.assertRaises(RuntimeDependencyError):
            calculate_sample_size({"test_key": "proportion_paired", "parameters": parameters}, engine=MissingRuntime())


if __name__ == "__main__": unittest.main()
