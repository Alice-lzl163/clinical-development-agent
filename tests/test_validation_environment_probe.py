import unittest
from pathlib import Path

import yaml

from sample_size.validation.environment_probe import _probe_package, probe


class ValidationEnvironmentProbeTests(unittest.TestCase):
    def test_windows_paths_are_output_data_not_interpolated_r_source(self):
        windows_paths=[r"C:\R\bin\Rscript.exe",r"C:\Program Files\R\R-4.6.1\bin\Rscript.exe",r"C:\Users\Example User\Documents\R\win-library\4.6"]
        for library_path in windows_paths:
            calls=[]
            completed=type("Completed",(),{"returncode":0,"stdout":f"pwr\tTRUE\t1.3.0\t{library_path}\tTRUE|TRUE","stderr":""})()
            def runner(arguments,**kwargs): calls.append((arguments,kwargs)); return completed
            with self.subTest(path=library_path):
                result=_probe_package(windows_paths[1],"pwr",["pwr.t.test","pwr.anova.test"],runner=runner)
                self.assertEqual(library_path,result["library_path"])
                arguments,kwargs=calls[0]
                self.assertEqual(windows_paths[1],arguments[0]); self.assertIsInstance(arguments,list)
                self.assertNotIn(library_path,arguments[-1]); self.assertEqual("pwr",kwargs["env"]["CDA_PACKAGE"])
                self.assertEqual("pwr.t.test|pwr.anova.test",kwargs["env"]["CDA_FUNCTIONS"])
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
