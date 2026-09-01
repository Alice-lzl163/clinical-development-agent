import unittest
from pathlib import Path

import yaml

from sample_size.validation.environment_probe import probe


class ValidationEnvironmentProbeTests(unittest.TestCase):
    def test_probe_is_machine_readable_and_non_installing(self):
        result=probe()
        self.assertIn(result["rscript"]["status"],{"FOUND","NOT_FOUND"})
        self.assertIn(result["scipy"]["status"],{"FOUND","NOT_FOUND"})
        self.assertEqual(0,result["live_calculations_executed"])

    def test_dependency_blocked_summary_does_not_promote_methods(self):
        path=Path(__file__).resolve().parents[1]/"sample_size"/"validation"/"validation_summary.yaml"
        summary=yaml.safe_load(path.read_text(encoding="utf-8"))
        self.assertEqual("DEPENDENCY_BLOCKED",summary["outcome"])
        self.assertEqual({"total":24,"numerically_executed":0,"passed":0,"failed":0,"pending":24},summary["benchmarks"])
        self.assertEqual(6,len(summary["methods"]))
        for method in summary["methods"]:
            self.assertEqual("IMPLEMENTED_UNVALIDATED",method["validation_status"])
            self.assertEqual("BLOCKED",method["package_reproduction"])
            self.assertIsNone(method["validated_R_version"])
            self.assertIsNone(method["validated_package_version"])


if __name__ == "__main__": unittest.main()
