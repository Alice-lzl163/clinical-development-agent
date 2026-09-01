import copy
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "sample_size" / "specs"
with (SPEC_DIR / "schema.json").open(encoding="utf-8") as stream:
    SCHEMA = yaml.safe_load(stream)
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)

EXPECTED_KEYS = {
    "ttest_ind", "ttest_paired", "ttest_one", "anova", "equivalence", "mixed_model",
    "proportion_two", "proportion_one", "proportion_paired", "odds_ratio", "risk_ratio",
    "non_inferiority", "superiority_margin", "be_tost", "vaccine_efficacy", "gsd_proportion",
    "poisson", "recurrent_events", "gsd_poisson", "survival", "survival_exact", "ni_survival",
    "survival_equivalence", "survival_superiority", "cox_covariate", "survival_one_sample",
    "competing_risks", "survival_historical", "gsd_survival", "gsd_hazard",
    "gsd_survival_sim", "gsd_hazard_sim", "roc", "bland_altman", "group_sequential",
    "adaptive", "adaptive_simulate", "bayesian", "dose_escalation", "mams", "dunnett",
    "win_ratio", "must_win", "historical_controls", "conditional_power", "assurance",
    "multiple_endpoints", "mediation", "cluster"
}


def load_yaml(path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def semantic_errors(spec):
    errors = []
    input_names = [item["name"] for item in spec.get("inputs", []) if isinstance(item, dict) and "name" in item]
    if len(input_names) != len(set(input_names)):
        errors.append("duplicate input names")

    formal_names = [item["name"] for item in spec.get("engine", {}).get("formal_arguments", []) if isinstance(item, dict) and "name" in item]
    if len(formal_names) != len(set(formal_names)):
        errors.append("duplicate formal argument names")

    for item in spec.get("inputs", []):
        value, limits = item.get("default"), item.get("valid_range")
        if value is None or limits is None:
            continue
        name = item.get("name", "<unnamed>")
        if "minimum" in limits and value < limits["minimum"]:
            errors.append(f"{name} default below minimum")
        if "maximum" in limits and value > limits["maximum"]:
            errors.append(f"{name} default above maximum")
        if "exclusive_minimum" in limits and value <= limits["exclusive_minimum"]:
            errors.append(f"{name} default not above exclusive_minimum")
        if "exclusive_maximum" in limits and value >= limits["exclusive_maximum"]:
            errors.append(f"{name} default not below exclusive_maximum")
        if "allowed_values" in limits and value not in limits["allowed_values"]:
            errors.append(f"{name} default not in allowed_values")
    return errors


def validation_errors(spec):
    schema_errors = [error.message for error in VALIDATOR.iter_errors(spec)]
    return schema_errors + semantic_errors(spec)


class SpecSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(SPEC_DIR.glob("*.yaml"))
        cls.specs = [load_yaml(path) for path in cls.paths]
        cls.by_key = {spec["test_key"]: spec for spec in cls.specs}

    def assert_invalid(self, spec):
        self.assertTrue(validation_errors(spec), "mutated specification unexpectedly validated")

    def mutated_input_default(self, test_key, input_name, value):
        spec = copy.deepcopy(self.by_key[test_key])
        next(item for item in spec["inputs"] if item["name"] == input_name)["default"] = value
        return spec

    def test_49_specs_found_and_valid(self):
        self.assertEqual(49, len(self.specs))
        self.assertEqual(EXPECTED_KEYS, set(self.by_key))
        for path, spec in zip(self.paths, self.specs):
            with self.subTest(path=path.name):
                self.assertEqual([], validation_errors(spec))

    def test_filename_matches_key(self):
        for path, spec in zip(self.paths, self.specs):
            self.assertEqual(path.stem, spec["test_key"])

    def test_lifecycle_is_not_released(self):
        self.assertTrue(all(s["lifecycle_status"] in {"EXPERIMENTAL", "VALIDATION_PENDING"} for s in self.specs))

    def test_v4_v5_forbid_historical_behavior(self):
        for spec in self.specs:
            if spec["validation_grade"] in {"V4", "V5"}:
                self.assertTrue(any(w.startswith("DO_NOT_REPRODUCE_HISTORICAL_BEHAVIOR:") for w in spec["warnings"]), spec["test_key"])

    def test_simulation_and_oc_methods_expose_operating_characteristics(self):
        for spec in self.specs:
            if spec["method_type"] in {"simulation", "operating_characteristics"}:
                self.assertTrue(spec["solve_modes"]["operating_characteristics"], spec["test_key"])

    def test_invalid_alpha(self):
        self.assert_invalid(self.mutated_input_default("ttest_ind", "alpha", 1.0))

    def test_invalid_probability(self):
        self.assert_invalid(self.mutated_input_default("proportion_two", "control_probability", 1.1))

    def test_negative_sd(self):
        self.assert_invalid(self.mutated_input_default("equivalence", "sd", -0.1))

    def test_invalid_hr_rr_or(self):
        for key, name in [("survival", "alternative_hazard_ratio"), ("risk_ratio", "alternative_risk_ratio"), ("odds_ratio", "alternative_odds_ratio")]:
            with self.subTest(key=key):
                self.assert_invalid(self.mutated_input_default(key, name, 0))

    def test_duplicate_input_names(self):
        spec = copy.deepcopy(self.by_key["ttest_ind"])
        spec["inputs"].append(copy.deepcopy(spec["inputs"][0]))
        self.assert_invalid(spec)

    def test_unknown_yaml_field(self):
        spec = copy.deepcopy(self.by_key["ttest_ind"])
        spec["unknown_field"] = True
        self.assert_invalid(spec)

    def test_invalid_lifecycle_status(self):
        spec = copy.deepcopy(self.by_key["ttest_ind"])
        spec["lifecycle_status"] = "PRODUCTION"
        self.assert_invalid(spec)

    def test_package_function_without_package(self):
        spec = copy.deepcopy(self.by_key["ttest_ind"])
        spec["engine"]["package"] = None
        self.assert_invalid(spec)

    def test_package_function_without_formal_arguments(self):
        spec = copy.deepcopy(self.by_key["ttest_ind"])
        spec["engine"]["formal_arguments"] = []
        self.assert_invalid(spec)


if __name__ == "__main__":
    unittest.main()
