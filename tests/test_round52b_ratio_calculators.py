import math
import unittest

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageExecutionError, RequestValidationError, RuntimeDependencyError


class RecordingEngine:
    def __init__(self, raw): self.raw = raw; self.calls = []
    def execute(self, **kwargs): self.calls.append(kwargs); return dict(self.raw)


def inverse_raw(**changes):
    value = {
        "package_total": 527.7, "package_n1": 351.8, "package_n2": 175.9,
        "analysis_n_treatment": 352, "analysis_n_control": 176,
        "achieved_power": .801, "constrained_null_p1": .31,
        "constrained_null_p2": .27, "checked_n1": 352.0, "checked_n2": 176.0,
        "rounding_increments": 0, "realized_package_ratio": .5,
        "package_version": "3.11.0", "r_version": "R version 4.6.1 (test)",
        "session_info": "test", "warnings": [],
    }
    value.update(changes); return value


def request(key, **changes):
    ratio = "odds" if key == "odds_ratio" else "risk"
    value = {"control_probability": .2, f"alternative_{ratio}_ratio": 2.0,
             f"null_{ratio}_ratio": 1.2, "allocation_ratio": 2,
             "alpha": .025, "power": .8, "dropout_rate": .1}
    value.update(changes); return {"test_key": key, "parameters": value}


class Round52BRatioCalculatorTests(unittest.TestCase):
    def test_or_transformation_mapping_rounding_dropout_and_status(self):
        engine = RecordingEngine(inverse_raw())
        result = calculate_sample_size(request("odds_ratio"), engine=engine)
        treatment = 2*.2/(1-.2+2*.2)
        inverse = result.package_arguments["inverse"]
        self.assertAlmostEqual(treatment, inverse["p1"])
        self.assertEqual(.2, inverse["p2"])
        self.assertAlmostEqual(math.log(1.2), inverse["delta0"])
        self.assertEqual(.5, inverse["ratio"])
        self.assertEqual("OR", inverse["scale"])
        self.assertEqual(1, inverse["sided"]); self.assertEqual(3, inverse["outtype"])
        self.assertIsNone(inverse["n"])
        self.assertEqual({"treatment": 352, "control": 176}, result.sample_size_per_group)
        self.assertEqual(528, result.analysis_required_sample_size)
        self.assertEqual(math.ceil(352/.9)+math.ceil(176/.9), result.randomized_sample_size)
        self.assertAlmostEqual(treatment, result.derived_parameters["alternative_treatment_probability"])
        self.assertEqual("IMPLEMENTED_UNVALIDATED", result.validation_status)
        self.assertEqual("round-5.2b", result.implementation_version)
        self.assertEqual("not_assigned", result.benchmark_id)
        self.assertIn("gsDesign::nBinomial", result.reproducible_code)
        self.assertIn("while (checked$power", result.reproducible_code)

    def test_rr_transformation_and_inverse_arguments(self):
        engine = RecordingEngine(inverse_raw(package_total=731.4, package_n1=487.6, package_n2=243.8, analysis_n_treatment=488, analysis_n_control=244, checked_n1=488, checked_n2=244))
        result = calculate_sample_size(request("risk_ratio", alternative_risk_ratio=1.75), engine=engine)
        inverse = result.package_arguments["inverse"]
        self.assertAlmostEqual(.35, inverse["p1"])
        self.assertEqual(.2, inverse["p2"])
        self.assertEqual("RR", inverse["scale"])
        self.assertAlmostEqual(math.log(1.2), inverse["delta0"])
        self.assertEqual(.5, inverse["ratio"])
        self.assertEqual({"treatment": 488, "control": 244}, result.sample_size_per_group)

    def test_power_mode_uses_analyzable_total_and_realized_ratio(self):
        raw = inverse_raw(achieved_power=.77, checked_n1=80.0, checked_n2=41.0, realized_package_ratio=41/80)
        engine = RecordingEngine(raw)
        parameters = {"control_probability": .2, "alternative_risk_ratio": 1.75,
                      "null_risk_ratio": 1.2, "alpha": .025,
                      "analyzable_treatment": 80, "analyzable_control": 41}
        result = calculate_sample_size({"test_key": "risk_ratio", "solve_mode": "power", "parameters": parameters}, engine=engine)
        self.assertEqual(121, result.analysis_required_sample_size)
        self.assertIsNone(result.randomized_sample_size)
        self.assertEqual(121, result.package_arguments["n"])
        self.assertEqual(41/80, result.package_arguments["ratio"])
        self.assertIsNone(result.package_arguments["beta"])
        self.assertEqual(.77, result.achieved_power)
        self.assertEqual("IMPLEMENTED_UNVALIDATED", result.validation_status)
        with self.assertRaises(RequestValidationError):
            calculate_sample_size({"test_key": "risk_ratio", "solve_mode": "power", "parameters": {**parameters, "allocation_ratio": 2}}, engine=engine)

    def test_invalid_direction_feasibility_and_unknown_operational_counts(self):
        for key, changes in (("risk_ratio", {"alternative_risk_ratio": 1.1}),
                             ("odds_ratio", {"alternative_odds_ratio": 1.1}),
                             ("risk_ratio", {"alternative_risk_ratio": 6.0})):
            with self.subTest(key=key, changes=changes), self.assertRaises(RequestValidationError):
                calculate_sample_size(request(key, **changes), engine=RecordingEngine(inverse_raw()))
        bad = request("odds_ratio"); bad["parameters"]["randomized_treatment"] = 400
        with self.assertRaises(RequestValidationError): calculate_sample_size(bad, engine=RecordingEngine(inverse_raw()))

    def test_inconsistent_or_nonfinite_package_outputs_fail_closed(self):
        cases = [inverse_raw(package_total=999), inverse_raw(package_n1=float("nan")), inverse_raw(checked_n2=175.5), inverse_raw(achieved_power=float("inf"))]
        for raw in cases:
            with self.subTest(raw=raw), self.assertRaises(PackageExecutionError):
                calculate_sample_size(request("odds_ratio"), engine=RecordingEngine(raw))

    def test_missing_gsdesign_failure_propagates_without_fallback(self):
        class MissingPackage:
            def execute(self, **_): raise RuntimeDependencyError("DEPENDENCY_MISSING: gsDesign")
        with self.assertRaises(RuntimeDependencyError):
            calculate_sample_size(request("risk_ratio"), engine=MissingPackage())


if __name__ == "__main__": unittest.main()
