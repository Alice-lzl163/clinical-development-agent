import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from sample_size.agent.validation import load_frozen_spec, validate_request
from sample_size.engines.errors import RequestValidationError

ROOT=Path(__file__).resolve().parents[1]
SPEC_PATH=ROOT/'sample_size/specs/equivalence.yaml'

class EquivalenceRepairedSpecificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec=yaml.safe_load(SPEC_PATH.read_text(encoding='utf-8'))
        cls.schema=yaml.safe_load((SPEC_PATH.parent/'schema.json').read_text(encoding='utf-8'))

    def test_refrozen_exact_powertost_contract(self):
        s=self.spec; self.assertEqual([],list(Draft202012Validator(self.schema).iter_errors(s)))
        self.assertEqual('SPEC_FROZEN',s['specification_status'])
        self.assertEqual('VALIDATION_PENDING',s['lifecycle_status'])
        self.assertEqual('mean_parallel_equivalence_symmetric_exact_tost',s['method_id'])
        self.assertEqual(('PowerTOST','PowerTOST::power.TOST'),(s['engine']['package'],s['engine']['function']))
        mappings={m['package_argument']:m for m in s['engine']['parameter_mapping']}
        expected={'logscale':False,'design':'parallel','method':'exact','robust':False}
        self.assertEqual(expected,{k:mappings[k]['source'] for k in expected})
        self.assertEqual(('expected_difference','lower_equivalence_bound','upper_equivalence_bound','sd'),(mappings['theta0']['source'],mappings['theta1']['source'],mappings['theta2']['source'],mappings['CV']['source']))
        self.assertNotIn('TrialSize',yaml.safe_dump(s['engine']))

    def test_public_allocation_and_search_are_closed(self):
        self.assertEqual('n_treatment / n_control',self.spec['allocation']['ratio_definition'])
        search=self.spec['sample_size_search']
        self.assertEqual((2,1000000),(search['minimum_per_arm'],search['maximum_per_arm']))
        self.assertEqual(('analyzable_control',1),(search['enumeration_variable'],search['enumeration_step']))
        self.assertEqual('ceil(allocation_ratio * analyzable_control)',search['candidate_mapping']['analyzable_treatment'])
        self.assertEqual('achieved_power >= target_power',search['acceptance_rule'])
        self.assertEqual('first_accepted_control_size',search['tie_breaking_rule'])
        self.assertEqual('raise_calculation_convergence_error_no_result',search['failure_behavior'])

    def test_power_mode_requires_only_explicit_analyzable_counts(self):
        inputs={i['name']:i for i in self.spec['inputs']}
        self.assertTrue(self.spec['solve_modes']['power'])
        self.assertEqual(['power'],inputs['analyzable_treatment']['required_for_solve_modes'])
        self.assertEqual(['power'],inputs['analyzable_control']['required_for_solve_modes'])
        for name in ('power','dropout_rate','allocation_ratio'):
            self.assertEqual(['sample_size'],inputs[name]['allowed_for_solve_modes'])

    def test_domain_and_output_contract_are_explicit(self):
        inputs={i['name']:i for i in self.spec['inputs']}
        self.assertEqual({'exclusive_minimum':0},inputs['sd']['valid_range'])
        self.assertEqual({'exclusive_minimum':0},inputs['equivalence_margin']['valid_range'])
        self.assertEqual({'exclusive_minimum':0},inputs['allocation_ratio']['valid_range'])
        self.assertEqual({'exclusive_minimum':0,'exclusive_maximum':1},inputs['alpha']['valid_range'])
        self.assertEqual({'exclusive_minimum':0,'exclusive_maximum':1},inputs['power']['valid_range'])
        unsupported=' '.join(self.spec['unsupported_domains'])
        for text in ('abs(expected_difference)','Bioequivalence','Crossover','Asymmetric','Unequal population variances','Covariate-adjusted'):
            self.assertIn(text,unsupported)
        outputs={d['name'] for d in self.spec['derived_parameters']}
        self.assertTrue({'analyzable_total','randomized_treatment','randomized_control','randomized_total','realized_allocation_ratio'}<=outputs)

    def test_invalid_domains_and_mode_inputs_fail_closed(self):
        base={'expected_difference':0.1,'sd':1,'equivalence_margin':0.5,'allocation_ratio':2,'alpha':0.05,'power':0.8,'dropout_rate':0}
        for update in ({'sd':0},{'equivalence_margin':0},{'allocation_ratio':0},{'alpha':0},{'alpha':1},{'power':0},{'expected_difference':0.5}):
            with self.subTest(update=update), self.assertRaises(RequestValidationError):
                validate_request(load_frozen_spec('equivalence'),'sample_size',{**base,**update})
        power={'expected_difference':0.1,'sd':1,'equivalence_margin':0.5,'alpha':0.05,'analyzable_treatment':100,'analyzable_control':50}
        self.assertEqual(100,validate_request(load_frozen_spec('equivalence'),'power',power)['analyzable_treatment'])
        with self.assertRaises(RequestValidationError): validate_request(load_frozen_spec('equivalence'),'power',{**power,'dropout_rate':.1})

if __name__=='__main__': unittest.main()
