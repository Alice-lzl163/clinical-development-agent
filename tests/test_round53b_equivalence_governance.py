import json
import math
import unittest
from pathlib import Path

from scipy.stats import norm

from sample_size.validation.reference import mean_equivalence_exact_tost_power

ROOT=Path(__file__).resolve().parents[1]

class EquivalenceContractGovernanceTests(unittest.TestCase):
    def test_trialsize_formula_and_round53_defect_are_preserved(self):
        evidence=json.loads((ROOT/'sample_size/validation/round5_fixed_design_evidence.json').read_text())
        for fixture_id in ('eq_k2','eq_khalf'):
            row=evidence['fixtures'][fixture_id]; x=row['clinical_inputs']; beta=1-x['power']
            n2=(norm.ppf(1-x['alpha'])+norm.ppf(1-beta/2))**2*x['sd']**2*(1+1/x['allocation_ratio'])/(x['equivalence_margin']-abs(x['expected_difference']))**2
            self.assertAlmostEqual(x['allocation_ratio']*n2,row['raw_authoritative_outputs']['package_n_treatment'],11)
            self.assertEqual('FAIL',row['independent_reference']['status'])
            self.assertGreater(row['independent_reference']['absolute_difference'],.04)

    def test_exact_joint_tost_reference_confirms_nonzero_difference_defect(self):
        p1=mean_equivalence_exact_tost_power(n_treatment=161,n_control=81,difference=.1,sd=1,margin=.5,alpha=.05)
        p2=mean_equivalence_exact_tost_power(n_treatment=147,n_control=293,difference=-.1,sd=1.2,margin=.5,alpha=.05)
        self.assertAlmostEqual(0.8972844142785337,p1,12)
        self.assertAlmostEqual(0.9498308356241735,p2,12)
        self.assertGreater(abs(p1-.8034682368420658),.08)
        self.assertGreater(abs(p2-.9016900119055906),.03)
        self.assertTrue(math.isfinite(p1) and math.isfinite(p2))

if __name__=='__main__': unittest.main()
