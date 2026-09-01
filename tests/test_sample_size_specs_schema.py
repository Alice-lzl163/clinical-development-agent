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

    for component in spec.get("design_components", []):
        field_names = [field["name"] for field in component["fields"]]
        if len(field_names) != len(set(field_names)):
            errors.append(f"duplicate fields in {component['name']}")

    key = spec.get("test_key")
    if spec.get("specification_status") == "SPEC_FROZEN":
        mappings = spec.get("engine", {}).get("parameter_mapping", [])
        if any(m.get("source_type") == "unresolved" for m in mappings):
            errors.append("frozen specification has unresolved mapping")
        if key == "ttest_ind":
            ratio = next(i for i in spec["inputs"] if i["name"] == "allocation_ratio")
            if ratio["valid_range"] != {"allowed_values": [1]} or spec["allocation"]["supported"]:
                errors.append("independent t test must use equal allocation")
        if key == "ttest_paired" and ("paired" not in spec["display_name"].lower() or "crossover" in spec["display_name"].lower()):
            errors.append("paired design mislabeled")
        if key == "anova" and (spec["alpha"]["sidedness"] != "not_applicable" or spec["allocation"]["supported"]):
            errors.append("ANOVA must specify omnibus upper-tail equal allocation")
        if key == "proportion_two":
            orientation = {(m["package_argument"], m["source"]) for m in mappings}
            if not {("p1", "treatment_probability"), ("p2", "control_probability"), ("k", "allocation_ratio")} <= orientation:
                errors.append("TrialSize arm orientation is incorrect")
        if key == "be_tost" and not any(d["name"] == "randomized_total" and "sequence_block_size" in d["formula"] for d in spec["derived_parameters"]):
            errors.append("bioequivalence sequence-balanced enrollment rule missing")
        if key in {"group_sequential", "gsd_proportion", "gsd_survival"}:
            seq = next((c for c in spec["design_components"] if c["component_type"] == "SequentialDesignSpec"), None)
            required = {"number_of_looks", "information_rates", "overall_alpha", "target_power", "sidedness", "efficacy_boundary_type", "futility_boundary_type", "binding_futility", "alpha_spending_parameters", "beta_spending_parameters"}
            if seq is None or {f["name"] for f in seq["fields"]} != required:
                errors.append("incomplete sequential design")
            else:
                adapter_pairs = {(m["package_argument"], m["source"]) for m in seq["adapter"]["parameter_mapping"]}
                if not {("alpha", "sequential_design.overall_alpha"), ("beta", "sequential_design.target_power")} <= adapter_pairs:
                    errors.append("alpha/power not traceable through design construction")
        if key in {"survival_exact", "gsd_survival"}:
            components = {c["component_type"]: c for c in spec["design_components"]}
            for component_type in {"SurvivalEndpointSpec", "DropoutSpec"}:
                dist = next(f for f in components[component_type]["fields"] if f["name"] == "distribution")
                if dist["valid_range"].get("allowed_values") != ["exponential"]:
                    errors.append("unsupported survival distribution")
            dropout = next(f for f in components["DropoutSpec"]["fields"] if f["name"] == "cumulative_dropout_probability")
            horizon = next(f for f in components["DropoutSpec"]["fields"] if f["name"] == "dropout_horizon")
            if dropout["default"] and horizon["default"] is None:
                errors.append("positive dropout probability requires horizon")
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

    def test_independent_t_rejects_unequal_allocation(self):
        self.assert_invalid(self.mutated_input_default("ttest_ind", "allocation_ratio", 2))

    def test_paired_t_rejects_crossover_label(self):
        spec = copy.deepcopy(self.by_key["ttest_paired"]); spec["display_name"] = "2x2 crossover"
        self.assert_invalid(spec)

    def test_anova_rejects_unequal_allocation(self):
        spec = copy.deepcopy(self.by_key["anova"]); spec["allocation"]["supported"] = True
        self.assert_invalid(spec)

    def test_trialsize_orientation_is_frozen(self):
        spec = copy.deepcopy(self.by_key["proportion_two"])
        next(m for m in spec["engine"]["parameter_mapping"] if m["package_argument"] == "p1")["source"] = "control_probability"
        self.assert_invalid(spec)

    def test_bioequivalence_requires_sequence_balanced_enrollment(self):
        spec = copy.deepcopy(self.by_key["be_tost"]); next(d for d in spec["derived_parameters"] if d["name"] == "randomized_total")["formula"] = "ceil(evaluable_total)"
        self.assert_invalid(spec)

    def test_sequential_component_cannot_be_incomplete(self):
        spec = copy.deepcopy(self.by_key["group_sequential"]); spec["design_components"][0]["fields"].pop()
        self.assert_invalid(spec)

    def test_survival_positive_dropout_requires_horizon(self):
        spec = copy.deepcopy(self.by_key["survival_exact"]); fields = next(c for c in spec["design_components"] if c["component_type"] == "DropoutSpec")["fields"]
        next(f for f in fields if f["name"] == "cumulative_dropout_probability")["default"] = 0.1
        self.assert_invalid(spec)

    def test_survival_rejects_non_exponential_distribution(self):
        spec = copy.deepcopy(self.by_key["survival_exact"]); fields = next(c for c in spec["design_components"] if c["component_type"] == "SurvivalEndpointSpec")["fields"]
        next(f for f in fields if f["name"] == "distribution")["valid_range"]["allowed_values"] = ["weibull"]
        self.assert_invalid(spec)

    def test_sequential_alpha_power_are_traceable(self):
        spec = copy.deepcopy(self.by_key["gsd_proportion"]); spec["design_components"][0]["adapter"]["parameter_mapping"] = [m for m in spec["design_components"][0]["adapter"]["parameter_mapping"] if m["package_argument"] != "beta"]
        self.assert_invalid(spec)

    def test_frozen_specs_have_no_vague_or_unresolved_mappings(self):
        vague = ("documented arguments", "median/lambda inputs", "follow-up/event-time mapping")
        for spec in self.specs:
            if spec["specification_status"] == "SPEC_FROZEN":
                text = yaml.safe_dump(spec["engine"]["parameter_mapping"]).lower()
                self.assertFalse(any(term in text for term in vague), spec["test_key"])
                self.assertFalse(any(m["source_type"] == "unresolved" for m in spec["engine"]["parameter_mapping"]), spec["test_key"])


if __name__ == "__main__":
    unittest.main()
