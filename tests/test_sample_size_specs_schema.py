import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "sample_size" / "specs"
SCHEMA = json.loads((SPEC_DIR / "schema.json").read_text(encoding="utf-8"))
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


def resolve_ref(schema, ref):
    value = schema
    for part in ref.removeprefix("#/").split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def validate(instance, rule, root, path="$"):
    if "$ref" in rule:
        return validate(instance, resolve_ref(root, rule["$ref"]), root, path)
    if "enum" in rule and instance not in rule["enum"]:
        raise AssertionError(f"{path}: {instance!r} is not in {rule['enum']!r}")
    types = rule.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "boolean": lambda x: isinstance(x, bool),
                  "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
                  "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None}
        if not any(checks[t](instance) for t in types):
            raise AssertionError(f"{path}: expected {types}, got {type(instance).__name__}")
    if isinstance(instance, dict):
        missing = set(rule.get("required", [])) - set(instance)
        if missing:
            raise AssertionError(f"{path}: missing {sorted(missing)}")
        if rule.get("additionalProperties") is False:
            extra = set(instance) - set(rule.get("properties", {}))
            if extra:
                raise AssertionError(f"{path}: unexpected {sorted(extra)}")
        for key, value in instance.items():
            if key in rule.get("properties", {}):
                validate(value, rule["properties"][key], root, f"{path}.{key}")
    if isinstance(instance, list):
        if len(instance) < rule.get("minItems", 0):
            raise AssertionError(f"{path}: fewer than minItems")
        if "items" in rule:
            for index, value in enumerate(instance):
                validate(value, rule["items"], root, f"{path}[{index}]")
    if isinstance(instance, str):
        if len(instance) < rule.get("minLength", 0):
            raise AssertionError(f"{path}: shorter than minLength")
        if "pattern" in rule and not re.match(rule["pattern"], instance):
            raise AssertionError(f"{path}: does not match {rule['pattern']}")


class SpecSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = sorted(SPEC_DIR.glob("*.yaml"))
        cls.specs = [json.loads(path.read_text(encoding="utf-8")) for path in cls.paths]

    def test_exactly_49_specs(self):
        self.assertEqual(49, len(self.specs))
        self.assertEqual(EXPECTED_KEYS, {s["test_key"] for s in self.specs})

    def test_schema(self):
        for path, spec in zip(self.paths, self.specs):
            with self.subTest(path=path.name):
                validate(spec, SCHEMA, SCHEMA)

    def test_filename_matches_key_and_inputs_are_unique(self):
        for path, spec in zip(self.paths, self.specs):
            self.assertEqual(path.stem, spec["test_key"])
            names = [item["name"] for item in spec["inputs"]]
            self.assertEqual(len(names), len(set(names)), spec["test_key"])

    def test_lifecycle_is_not_released(self):
        self.assertTrue(all(s["lifecycle_status"] in {"EXPERIMENTAL", "VALIDATION_PENDING"} for s in self.specs))

    def test_v4_v5_forbid_historical_behavior(self):
        for spec in self.specs:
            if spec["validation_grade"] in {"V4", "V5"}:
                self.assertTrue(any(w.startswith("DO_NOT_REPRODUCE_HISTORICAL_BEHAVIOR:") for w in spec["warnings"]), spec["test_key"])

    def test_package_functions_have_signatures(self):
        for spec in self.specs:
            engine = spec["engine"]
            if engine["function"] is not None:
                self.assertIsNotNone(engine["package"], spec["test_key"])
                self.assertTrue(engine["function_signature"], spec["test_key"])
            if engine["package"] is not None:
                self.assertTrue(spec["package_reference"].startswith("https://"), spec["test_key"])

    def test_simulation_methods_expose_operating_characteristics(self):
        for spec in self.specs:
            if spec["method_type"] == "simulation":
                self.assertTrue(spec["solve_modes"]["operating_characteristics"], spec["test_key"])


if __name__ == "__main__":
    unittest.main()
