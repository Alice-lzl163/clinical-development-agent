"""Generate cross-platform comparable Round 5 live qualification evidence."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path

import yaml

from sample_size import calculate_sample_size
from sample_size.engines.r_engine import RExecutionEngine
from sample_size.validation.environment_probe import _probe_package, probe

ROOT = Path(__file__).resolve().parents[2]
FIXED = ROOT / "sample_size/validation/benchmarks/round5_fixed_design.yaml"
EQUIVALENCE = ROOT / "sample_size/validation/benchmarks/round5_equivalence_powertost.yaml"
METHODS = ("proportion_one", "proportion_paired", "equivalence", "non_inferiority", "superiority_margin", "odds_ratio", "risk_ratio")
EXACT_PACKAGES = {"pwr": "1.3.0", "TrialSize": "1.4.1", "PowerTOST": "1.5.7", "gsDesign": "3.11.0", "jsonlite": "2.0.0"}
PACKAGE_FUNCTIONS = {"pwr": ["pwr.p.test"], "TrialSize": ["McNemar.Test", "TwoSampleProportion.NIS"], "PowerTOST": ["power.TOST"], "gsDesign": ["nBinomial"], "jsonlite": []}


class CountingEngine(RExecutionEngine):
    def __init__(self, rscript): super().__init__(rscript); self.executions = self.successes = self.failures = 0
    def execute(self, **kwargs):
        self.executions += 1
        try:
            value = super().execute(**kwargs); self.successes += 1; return value
        except Exception:
            self.failures += 1; raise


def _replay(engine, result):
    prefix = f"library({result.package})\n\n"
    code = result.reproducible_code.removeprefix(prefix)
    return engine.execute(package=result.package, function=result.function, calculation_code=code)


def _expected_cases():
    fixed = yaml.safe_load(FIXED.read_text(encoding="utf-8"))["cases"]
    fixed = [row for row in fixed if row["test_key"] in set(METHODS)-{"equivalence"} and row.get("validation_status") == "FROZEN_VALIDATED"]
    equivalence = yaml.safe_load(EQUIVALENCE.read_text(encoding="utf-8"))["cases"]
    return fixed + [{**row, "test_key": "equivalence"} for row in equivalence]


def _validate(engine, fixture):
    result = calculate_sample_size({"test_key": fixture["test_key"], "solve_mode": fixture["solve_mode"], "parameters": fixture["inputs"]}, engine=engine)
    replay = _replay(engine, result)
    expected_total = (fixture.get("integer_analyzable_outputs") or fixture.get("analyzable"))["total"]
    expected_groups = (fixture.get("integer_analyzable_outputs") or fixture.get("analyzable")).get("groups")
    expected_sequences = (fixture.get("integer_analyzable_outputs") or {}).get("sequences")
    expected_randomized = (fixture.get("randomized_outputs") or fixture.get("randomized"))["total"]
    expected_power = fixture["achieved_power"] if "achieved_power" in fixture else fixture["raw_authoritative_outputs"]["achieved_power"]
    tolerance = 1e-12 if fixture["test_key"] == "equivalence" else 1e-10
    checks = {
        "integer_total": result.analysis_required_sample_size == expected_total,
        "group_sizes": result.sample_size_per_group == expected_groups,
        "sequence_sizes": result.sample_size_per_sequence == expected_sequences,
        "randomized_total": result.randomized_sample_size == expected_randomized,
        "achieved_power": abs(result.achieved_power-expected_power) <= tolerance,
        "direct_replay": abs(float(replay["achieved_power"])-result.achieved_power) <= tolerance,
        "identity": result.test_key == fixture["test_key"] and result.benchmark_id in {"round5-fixed-design-v1", "round5-equivalence-powertost-v1"},
        "reproducibility": bool(result.reproducible_code and result.specification_version.startswith("sha256:")),
        "specification_hash": result.specification_version == fixture["spec_sha256"],
        "implementation_version": result.implementation_version == fixture["implementation_version"],
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "agent_result": result.to_dict(),
            "direct_replay": {"achieved_power": float(replay["achieved_power"]), "package_version": replay["package_version"], "r_version": replay["r_version"], "warnings": replay.get("warnings", [])}}


def run():
    environment = probe(); rscript = environment["rscript"].get("selected")
    if not rscript: raise RuntimeError("ENVIRONMENT_BLOCKED: Rscript unavailable")
    packages = {}
    for package, version in EXACT_PACKAGES.items():
        row = _probe_package(rscript, package, PACKAGE_FUNCTIONS[package]); packages[package] = row
        if row.get("status") != "FOUND" or row.get("version") != version or not all(row.get("functions", {}).values()):
            raise RuntimeError(f"DEPENDENCY_BLOCKED: exact {package} {version} contract unavailable")
    engine = CountingEngine(rscript)
    fixtures = {row["id"]: _validate(engine, row) for row in _expected_cases()}
    method_gates = {}
    for method in METHODS:
        rows = [value for key, value in fixtures.items() if value["agent_result"]["test_key"] == method]
        method_gates[method] = {"frozen_benchmark_regression": "PASS" if rows and all(row["status"] == "PASS" for row in rows) else "FAIL",
                                "direct_live_R": "PASS" if rows and all(row["checks"]["direct_replay"] for row in rows) else "FAIL",
                                "reproducibility": "PASS" if rows and all(row["checks"]["reproducibility"] for row in rows) else "FAIL"}
    preserved = [ROOT/"sample_size/validation/round42_evidence.json", ROOT/"sample_size/validation/round5_fixed_design_evidence.json", ROOT/"sample_size/validation/benchmarks/round5_fixed_design.yaml", ROOT/"sample_size/validation/round5_equivalence_powertost_evidence.json", ROOT/"sample_size/validation/benchmarks/round5_equivalence_powertost.yaml"]
    return {"schema_version": 1, "qualification_round": "5.4", "benchmark_ids": ["round5-fixed-design-v1", "round5-equivalence-powertost-v1"],
            "environment": {"probe": environment, "packages": packages, "Python": platform.python_version()},
            "live_execution": {"executed": engine.executions, "successful": engine.successes, "failed": engine.failures},
            "fixtures": fixtures, "method_gates": method_gates,
            "preserved_evidence_sha256": {str(path.relative_to(ROOT)).replace('\\','/'): hashlib.sha256(path.read_bytes()).hexdigest() for path in preserved},
            "status": "PASS" if all(row["status"] == "PASS" for row in fixtures.values()) and engine.failures == 0 else "FAIL"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--output", required=True); args = parser.parse_args()
    evidence = run(); Path(args.output).write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "fixtures": len(evidence["fixtures"]), "live_execution": evidence["live_execution"]}, indent=2))
    raise SystemExit(0 if evidence["status"] == "PASS" else 1)
