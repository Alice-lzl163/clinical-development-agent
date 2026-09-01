import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.errors import PackageContractError, PackageExecutionError, RequestValidationError, RuntimeDependencyError, UnknownMethodError, UnsupportedSolveModeError
from sample_size.engines.r_engine import RExecutionEngine


class StubEngine:
    def __init__(self, response): self.response = response; self.calls = []
    def execute(self, **call): self.calls.append(call); return dict(self.response)


def response(**values):
    return {"package_version": "TEST", "r_version": "R TEST", "session_info": "TEST", "warnings": [], **values}


class CalculatorTests(unittest.TestCase):
    def calculate(self, key, parameters, raw):
        engine = StubEngine(raw)
        return calculate_sample_size({"test_key": key, "parameters": parameters}, engine=engine), engine

    def test_one_sample_rounding_dropout_and_code(self):
        params={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":.1,"alternative":"two_sided"}
        result, engine=self.calculate("ttest_one",params,response(package_n=33.2,analysis_n=34,achieved_power=.81))
        self.assertEqual((34,38),(result.analysis_required_sample_size,result.randomized_sample_size)); self.assertIn('type = "one.sample"',result.reproducible_code); self.assertEqual("IMPLEMENTED_UNVALIDATED",result.validation_status)

    def test_paired_n_means_complete_participants(self):
        params={"standardized_paired_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"greater"}
        result,_=self.calculate("ttest_paired",params,response(package_n=27.1,analysis_n=28,achieved_power=.82))
        self.assertEqual(28,result.sample_size_per_sequence["complete_pairs_or_participants"]); self.assertEqual("one_sided",result.sidedness)

    def test_independent_equal_arms_and_dropout(self):
        params={"standardized_effect":.5,"allocation_ratio":1,"alpha":.05,"power":.8,"dropout_rate":.2,"alternative":"two_sided"}
        result,_=self.calculate("ttest_ind",params,response(package_n=63.8,analysis_n=64,achieved_power=.801))
        self.assertEqual({"treatment":64,"control":64},result.sample_size_per_group); self.assertEqual(160,result.randomized_sample_size)

    def test_anova_n_is_per_group(self):
        params={"groups":3,"cohen_f":.25,"alpha":.05,"power":.8,"dropout_rate":0}
        result,_=self.calculate("anova",params,response(package_n=32,analysis_n_per_group=32,achieved_power=.81))
        self.assertEqual(32,result.derived_parameters["analyzable_per_group"]); self.assertEqual(96,result.analysis_required_sample_size)

    def test_anova_dropout_preserves_balance(self):
        params={"groups":4,"cohen_f":.25,"alpha":.05,"power":.8,"dropout_rate":.1}
        result,_=self.calculate("anova",params,response(package_n=20.2,analysis_n_per_group=21,achieved_power=.81))
        self.assertEqual(24,result.derived_parameters["randomized_per_group"]); self.assertEqual(96,result.randomized_sample_size)

    def test_proportion_orientation(self):
        params={"control_probability":.2,"treatment_probability":.35,"allocation_ratio":2.,"alpha":.05,"power":.8,"dropout_rate":0}
        result,engine=self.calculate("proportion_two",params,response(package_n_treatment=150.2,analysis_n_treatment=151,analysis_n_control=76,achieved_power=.805))
        self.assertEqual({"treatment":151,"control":76},result.sample_size_per_group); code=engine.calls[0]["calculation_code"]; self.assertIn("p1 = 0.35",code); self.assertIn("p2 = 0.2",code); self.assertIn("k = 2.0",code)

    def test_be_distinguishes_evaluable_and_randomized_2x2(self):
        params={"cv":.2,"theta0":.95,"lower_limit":.8,"upper_limit":1.25,"design":"2x2","alpha":.05,"power":.8,"dropout_rate":.1}
        result,_=self.calculate("be_tost",params,response(package_n=24,evaluable_total=24,package_achieved_power=.82,achieved_power=.82))
        self.assertEqual((24,28),(result.analysis_required_sample_size,result.randomized_sample_size)); self.assertEqual({"TR":14,"RT":14},result.sample_size_per_sequence)

    def test_be_parallel_is_balanced(self):
        params={"cv":.4,"theta0":.95,"lower_limit":.8,"upper_limit":1.25,"design":"parallel","alpha":.05,"power":.8,"dropout_rate":.1}
        result,_=self.calculate("be_tost",params,response(package_n=24,evaluable_total=24,package_achieved_power=.82,achieved_power=.82))
        self.assertEqual({"treatment":14,"control":14},result.sample_size_per_group)

    def test_unknown_key_fails_closed(self):
        with self.assertRaises(UnknownMethodError): calculate_sample_size({"test_key":"adaptive","parameters":{}})

    def test_unknown_parameter_fails_closed(self):
        p={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided","invented":1}
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key":"ttest_one","parameters":p})

    def test_missing_required_input_fails_closed(self):
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key":"ttest_one","parameters":{}})

    def test_invalid_alternative_fails_closed(self):
        p={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"up"}
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key":"ttest_one","parameters":p})

    def test_less_alternative_does_not_silently_negate_effect(self):
        p={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"less"}
        with self.assertRaises(PackageContractError): calculate_sample_size({"test_key":"ttest_one","parameters":p}, engine=StubEngine({}))

    def test_independent_unequal_allocation_fails_closed(self):
        p={"standardized_effect":.5,"allocation_ratio":2,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided"}
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key":"ttest_ind","parameters":p})

    def test_be_unsupported_design_fails_closed(self):
        p={"cv":.2,"theta0":.95,"lower_limit":.8,"upper_limit":1.25,"design":"3x3","alpha":.05,"power":.8,"dropout_rate":0}
        with self.assertRaises(RequestValidationError): calculate_sample_size({"test_key":"be_tost","parameters":p})

    def test_public_power_mode_fails_on_underidentified_frozen_contract(self):
        p={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided"}
        with self.assertRaises(UnsupportedSolveModeError): calculate_sample_size({"test_key":"ttest_one","solve_mode":"power","parameters":p})

    def test_missing_r_is_dependency_error(self):
        if shutil.which("Rscript"): self.skipTest("Rscript is installed")
        p={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided"}
        with self.assertRaises(RuntimeDependencyError): calculate_sample_size({"test_key":"ttest_one","parameters":p})

    def test_benchmark_fixture_is_machine_readable_and_complete(self):
        path=Path(__file__).resolve().parents[1]/"sample_size"/"validation"/"benchmarks"/"fixed_design_round4.yaml"
        data=yaml.safe_load(path.read_text(encoding="utf-8")); self.assertGreaterEqual(len(data["cases"]),16)
        required={"inputs","expected_package_call","expected_raw_package_output","expected_analyzable_n","expected_randomized_n","expected_achieved_power","tolerance","source"}
        for case in data["cases"]: self.assertLessEqual(required,set(case),case["id"])

    def test_dropout_is_monotone_and_does_not_change_analyzable_n(self):
        base={"standardized_effect":.5,"allocation_ratio":1,"alpha":.05,"power":.8,"alternative":"two_sided"}
        totals=[]
        for dropout in (0,.1,.2):
            result,_=self.calculate("ttest_ind",{**base,"dropout_rate":dropout},response(package_n=63.8,analysis_n=64,achieved_power=.801))
            self.assertEqual(128,result.analysis_required_sample_size); totals.append(result.randomized_sample_size)
        self.assertEqual(sorted(totals),totals)

    def test_below_target_forward_power_fails(self):
        params={"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided"}
        with self.assertRaises(PackageExecutionError): self.calculate("ttest_one",params,response(package_n=33.2,analysis_n=34,achieved_power=.79))

    def test_adapters_execute_inverse_then_forward_power(self):
        cases=[
            ("ttest_one",{"standardized_effect":.5,"alpha":.05,"power":.8,"dropout_rate":0,"alternative":"two_sided"},response(package_n=34,analysis_n=34,achieved_power=.81),"forward <- pwr::pwr.t.test"),
            ("anova",{"groups":3,"cohen_f":.25,"alpha":.05,"power":.8,"dropout_rate":0},response(package_n=32,analysis_n_per_group=32,achieved_power=.81),"forward <- pwr::pwr.anova.test"),
            ("be_tost",{"cv":.2,"theta0":.95,"lower_limit":.8,"upper_limit":1.25,"design":"2x2","alpha":.05,"power":.8,"dropout_rate":0},response(package_n=24,evaluable_total=24,package_achieved_power=.82,achieved_power=.82),"forward_power <- PowerTOST::power.TOST"),
        ]
        for key,params,raw,needle in cases:
            with self.subTest(key=key):
                _,engine=self.calculate(key,params,raw); self.assertIn(needle,engine.calls[0]["calculation_code"])

    def test_r_engine_parses_only_marked_structured_json(self):
        completed=type("Completed",(),{"returncode":0,"stdout":"noise\n__CDA_SAMPLE_SIZE_JSON__{\"value\":3}","stderr":""})()
        with patch("sample_size.engines.r_engine.subprocess.run",return_value=completed):
            output=RExecutionEngine(rscript="Rscript").execute(package="pwr",function="pwr::pwr.t.test",calculation_code="list(value=3)")
        self.assertEqual({"value":3},output)

    def test_independent_reference_implementations_are_available(self):
        try:
            from sample_size.validation.reference import anova_power, t_test_power
            p_t=t_test_power(n=34,effect=.5,alpha=.05,test_type="one.sample",alternative="two.sided")
            p_f=anova_power(groups=3,n_per_group=53,cohen_f=.25,alpha=.05)
        except ImportError:
            self.skipTest("scipy is unavailable for validation-only references")
        self.assertGreater(p_t,.8); self.assertGreater(p_f,.8)


if __name__ == "__main__": unittest.main()
