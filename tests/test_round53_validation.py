import json
import math
import unittest
from pathlib import Path

import yaml

from sample_size.validation.reference import gsdesign_ratio_reference, mcnemar_power, one_proportion_arcsine_power

ROOT=Path(__file__).resolve().parents[1]

class Round53EvidenceTests(unittest.TestCase):
    def test_frozen_evidence_is_internally_consistent(self):
        evidence=json.loads((ROOT/'sample_size/validation/round5_fixed_design_evidence.json').read_text())
        summary=yaml.safe_load((ROOT/'sample_size/validation/round5_validation_summary.yaml').read_text())
        self.assertEqual('round5-fixed-design-v1',evidence['benchmark_id'])
        self.assertEqual(22,len(evidence['fixtures']))
        self.assertEqual(20,sum(x['status']=='PASS' for x in evidence['fixtures'].values()))
        self.assertEqual(96,evidence['live_execution']['successful'])
        self.assertEqual(20,summary['fixtures']['passed'])
        self.assertEqual('STATISTICAL_CONTRACT_DEFECT',evidence['method_gates']['equivalence']['blocker'])
        validated={k for k,v in evidence['method_gates'].items() if v['validation_status']=='BENCHMARK_VALIDATED'}
        self.assertEqual({'proportion_one','proportion_paired','non_inferiority','superiority_margin','odds_ratio','risk_ratio'},validated)

    def test_independent_reference_regressions(self):
        self.assertAlmostEqual(.8025683632434663,mcnemar_power(n=59,p01=.2,p10=.5,alpha=.05),12)
        self.assertGreater(one_proportion_arcsine_power(n=100,p1=.45,p0=.30,alpha=.05,alternative='greater'),.8)
        ref=gsdesign_ratio_reference(n_treatment=352,n_control=176,p1=1/3,p2=.2,null_ratio=1,alpha=.025,scale='OR')
        self.assertAlmostEqual(1,ref['p10']/(1-ref['p10'])/(ref['p20']/(1-ref['p20'])),12)
        self.assertTrue(math.isfinite(ref['power']))

if __name__=='__main__': unittest.main()
