import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = ROOT / "sample_size/specs"
KEYS = ("proportion_one", "proportion_paired", "equivalence", "non_inferiority", "superiority_margin", "odds_ratio", "risk_ratio")


class Round51SpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = {key: yaml.safe_load((SPEC_DIR / f"{key}.yaml").read_text(encoding="utf-8")) for key in KEYS}
        schema = yaml.safe_load((SPEC_DIR / "schema.json").read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(schema)

    def test_all_seven_specs_validate(self):
        for key, spec in self.specs.items():
            with self.subTest(key=key): self.assertEqual([], list(self.validator.iter_errors(spec)))

    def test_freeze_decisions_are_evidence_bounded(self):
        self.assertEqual({"odds_ratio", "risk_ratio"}, {key for key, spec in self.specs.items() if spec["specification_status"] == "DRAFT"})
        self.assertTrue(all(self.specs[key]["specification_status"] == "SPEC_FROZEN" for key in set(KEYS) - {"odds_ratio", "risk_ratio"}))

    def test_one_sample_orientation_and_power_contract(self):
        spec = self.specs["proportion_one"]
        self.assertEqual("binary_one_sample_arcsine", spec["method_id"])
        self.assertEqual("pwr::pwr.p.test", spec["engine"]["function"])
        self.assertEqual("2*asin(sqrt(alternative_probability)) - 2*asin(sqrt(null_probability))", spec["derived_parameters"][0]["formula"])
        inputs = {item["name"]: item for item in spec["inputs"]}
        self.assertEqual(["power"], inputs["analyzable_sample_size"]["required_for_solve_modes"])
        self.assertEqual(["sample_size"], inputs["power"]["allowed_for_solve_modes"])

    def test_mcnemar_uses_directional_discordances_not_marginals(self):
        spec = self.specs["proportion_paired"]
        self.assertEqual("TrialSize::McNemar.Test", spec["engine"]["function"])
        self.assertEqual("two_sided", spec["alpha"]["sidedness"])
        self.assertIn("qnorm(1-alpha/2)", spec["alpha"]["convention"])
        derived = {item["name"]: item["formula"] for item in spec["derived_parameters"]}
        self.assertEqual("p_treatment_only / p_control_only", derived["discordance_ratio"])
        self.assertEqual("p_treatment_only + p_control_only", derived["total_discordance_probability"])
        inputs = {item["name"]: item for item in spec["inputs"]}
        self.assertEqual(0, inputs["p_control_only"]["valid_range"]["exclusive_minimum"])
        self.assertEqual(0, inputs["p_treatment_only"]["valid_range"]["exclusive_minimum"])
        self.assertTrue(any("sum > 1" in item for item in spec["unsupported_domains"]))
        self.assertFalse(spec["solve_modes"]["power"])
        self.assertTrue(any("Marginal paired" in item for item in spec["unsupported_domains"]))

    def test_equivalence_is_symmetric_mean_tost_not_bioequivalence(self):
        spec = self.specs["equivalence"]
        names = {item["name"] for item in spec["inputs"]}
        self.assertIn("equivalence_margin", names); self.assertNotIn("lower_bound", names); self.assertNotIn("upper_bound", names)
        self.assertEqual("two_one_sided_tests", spec["alpha"]["sidedness"])
        alpha = next(item for item in spec["inputs"] if item["name"] == "alpha")
        self.assertIn("One-sided significance level", alpha["definition"])
        self.assertIn("does not divide", alpha["clinical_interpretation"])
        mappings = {item["package_argument"]: item["source"] for item in spec["engine"]["parameter_mapping"]}
        self.assertEqual("allocation_ratio", mappings["k"])
        self.assertEqual("equivalence_margin", mappings["delta"])
        self.assertEqual("expected_difference", mappings["margin"])
        self.assertIn("n1", spec["engine"]["output_mapping"][0]["package_output"])
        self.assertTrue(any("Bioequivalence" in item for item in spec["unsupported_domains"]))

    def test_margin_orientation_and_shared_method_identity(self):
        ni, sup = self.specs["non_inferiority"], self.specs["superiority_margin"]
        self.assertEqual(ni["method_id"], sup["method_id"])
        ni_derived = {item["name"]: item["formula"] for item in ni["derived_parameters"]}
        sup_derived = {item["name"]: item["formula"] for item in sup["derived_parameters"]}
        self.assertEqual("-noninferiority_margin", ni_derived["package_margin"])
        self.assertEqual("superiority_margin", sup_derived["package_margin"])
        self.assertIn("-noninferiority_margin", ni["hypothesis"]["null"])
        self.assertIn("superiority_margin", sup["hypothesis"]["null"])
        ni_inputs = {item["name"]: item for item in ni["inputs"]}
        sup_inputs = {item["name"]: item for item in sup["inputs"]}
        self.assertEqual(0, ni_inputs["noninferiority_margin"]["valid_range"]["exclusive_minimum"])
        self.assertEqual(0, sup_inputs["superiority_margin"]["valid_range"]["exclusive_minimum"])
        sup_margin = next(item for item in sup["derived_parameters"] if item["name"] == "package_margin")
        self.assertNotIn("NI", " ".join(sup_margin["assumptions"]))
        self.assertIn("passed directly", " ".join(sup_margin["assumptions"]))

    def test_or_rr_require_baseline_and_feasible_derived_risk(self):
        for key, scale in (("odds_ratio", "odds"), ("risk_ratio", "risk")):
            with self.subTest(key=key):
                spec = self.specs[key]; names = {item["name"] for item in spec["inputs"]}
                self.assertIn("control_probability", names)
                self.assertIn(f"alternative_{scale}_ratio", names); self.assertIn(f"null_{scale}_ratio", names)
                self.assertTrue(any("Infeasible" in item for item in spec["unsupported_domains"]))
                control = next(item for item in spec["inputs"] if item["name"] == "control_probability")
                self.assertEqual({"exclusive_minimum": 0, "exclusive_maximum": 1}, control["valid_range"])
                self.assertEqual("DRAFT", spec["specification_status"])
                self.assertTrue(any("gsDesign is not installed" in item for item in spec["unsupported_domains"]))

    def test_unsupported_power_mode_benchmarks_do_not_claim_public_power(self):
        for key in ("proportion_paired", "equivalence", "non_inferiority", "superiority_margin", "odds_ratio", "risk_ratio"):
            with self.subTest(key=key):
                spec = self.specs[key]
                self.assertFalse(spec["solve_modes"]["power"])
                benchmark = " ".join(spec["benchmark_requirements"])
                self.assertIn("independent", benchmark.lower())
                self.assertIn("not a supported public power solve mode", benchmark)

    def test_method_ids_identify_methods_not_keys(self):
        ids = {key: spec["method_id"] for key, spec in self.specs.items()}
        duplicates = {method_id: {key for key, value in ids.items() if value == method_id} for method_id in set(ids.values())}
        self.assertEqual({"non_inferiority", "superiority_margin"}, duplicates["binary_parallel_risk_difference_margin_normal"])
        self.assertTrue(all(len(keys) == 1 for method_id, keys in duplicates.items() if method_id != "binary_parallel_risk_difference_margin_normal"))


if __name__ == "__main__": unittest.main()
