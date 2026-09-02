"""Round 5.3D qualification for repaired exact mean equivalence TOST."""
import argparse
import hashlib
import json
import math
import platform
import subprocess
from datetime import date
from pathlib import Path

import scipy
import yaml

from sample_size import calculate_sample_size
from sample_size.engines.r_engine import RExecutionEngine
from sample_size.validation.environment_probe import _probe_package, probe
from sample_size.validation.reference import mean_equivalence_exact_tost_power

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "sample_size/validation/benchmarks/round5_equivalence_powertost.yaml"
EVIDENCE = ROOT / "sample_size/validation/round5_equivalence_powertost_evidence.json"
SUMMARY = ROOT / "sample_size/validation/round5_equivalence_validation_summary.yaml"
BENCHMARK_ID = "round5-equivalence-powertost-v1"
IMPLEMENTATION_VERSION = "round-5.3d"
SEED = 5_303_004
REPLICATES = 100_000
DIRECT_TOLERANCE = 1e-12
REFERENCE_TOLERANCE = 1e-9


class CountingEngine(RExecutionEngine):
    def __init__(self, rscript):
        super().__init__(rscript)
        self.executions = self.successes = self.failures = 0
        self.authoritative_calls = 0

    def execute(self, **kwargs):
        self.executions += 1
        try:
            result = super().execute(**kwargs)
            self.successes += 1
            self.authoritative_calls += int(result.get("authoritative_package_calls", 1))
            return result
        except Exception:
            self.failures += 1
            raise


def _agent(engine, solve_mode, inputs):
    return calculate_sample_size({"test_key": "equivalence", "solve_mode": solve_mode, "parameters": inputs}, engine=engine)


def _direct_power(engine, arguments):
    n = arguments["n"]
    code = f'''result <- PowerTOST::power.TOST(
  alpha = {arguments["alpha"]!r}, logscale = FALSE,
  theta0 = {arguments["theta0"]!r}, theta1 = {arguments["theta1"]!r}, theta2 = {arguments["theta2"]!r},
  CV = {arguments["CV"]!r}, n = c({n[0]}, {n[1]}), design = "parallel", method = "exact", robust = FALSE
)
list(achieved_power = as.numeric(result))'''
    return engine.execute(package="PowerTOST", function="PowerTOST::power.TOST", calculation_code=code), code


def _integral(result, inputs):
    nt, nc = result.sample_size_per_group["treatment"], result.sample_size_per_group["control"]
    return mean_equivalence_exact_tost_power(n_treatment=nt, n_control=nc,
        difference=inputs["expected_difference"], sd=inputs["sd"],
        margin=inputs["equivalence_margin"], alpha=inputs["alpha"])


def _validate_fixture(engine, fixture):
    result = _agent(engine, fixture["solve_mode"], fixture["inputs"])
    direct, direct_code = _direct_power(engine, result.package_arguments)
    exact_reference = _integral(result, fixture["inputs"])
    direct_difference = abs(result.achieved_power - float(direct["achieved_power"]))
    reference_difference = abs(result.achieved_power - exact_reference)
    minimality = True
    if fixture["solve_mode"] == "sample_size":
        minimality = result.achieved_power >= fixture["inputs"]["power"]
        if result.sample_size_per_group["control"] > 2:
            minimality = minimality and result.derived_parameters["preceding_candidate_power"] < fixture["inputs"]["power"]
        dropout = fixture["inputs"]["dropout_rate"]
        dropout_ok = result.randomized_sample_size == sum(math.ceil(n / (1-dropout)) for n in result.sample_size_per_group.values())
    else:
        dropout_ok = result.randomized_sample_size is None and result.target_power is None
    passed = direct_difference <= DIRECT_TOLERANCE and reference_difference <= REFERENCE_TOLERANCE and minimality and dropout_ok
    return {
        "status": "PASS" if passed else "FAIL", "solve_mode": fixture["solve_mode"],
        "clinical_inputs": fixture["inputs"], "historical_diagnostic_id": fixture.get("historical_diagnostic_id"),
        "exact_package_arguments": result.package_arguments, "analyzable": {"groups": result.sample_size_per_group, "total": result.analysis_required_sample_size},
        "randomized": {"treatment": result.derived_parameters["randomized_treatment"], "control": result.derived_parameters["randomized_control"], "total": result.randomized_sample_size},
        "achieved_power": result.achieved_power, "preceding_candidate_power": result.derived_parameters["preceding_candidate_power"],
        "search_iterations": result.derived_parameters["search_iterations"], "authoritative_calls_in_production": result.derived_parameters["authoritative_package_calls"],
        "direct_package": {"result": float(direct["achieved_power"]), "absolute_difference": direct_difference, "tolerance": DIRECT_TOLERANCE, "status": "PASS" if direct_difference <= DIRECT_TOLERANCE else "FAIL", "r_code": direct_code,
                           "r_version": direct["r_version"], "package_version": direct["package_version"], "warnings": direct.get("warnings", []), "session_info": direct["session_info"]},
        "independent_exact_integral": {"result": exact_reference, "absolute_difference": reference_difference, "tolerance": REFERENCE_TOLERANCE, "status": "PASS" if reference_difference <= REFERENCE_TOLERANCE else "FAIL"},
        "minimality": {"scope": "minimum control-arm N under ceil(allocation_ratio * control N), not global minimum total N", "status": "PASS" if minimality else "FAIL"},
        "dropout_and_result_contract": "PASS" if dropout_ok else "FAIL", "spec_sha256": result.specification_version,
        "implementation_version": result.implementation_version, "reproducible_r_code": result.reproducible_code,
    }


def _simulation(*, n_treatment, n_control, difference, sd, margin, alpha, exact_power, seed):
    import numpy as np
    from scipy.stats import t
    rng = np.random.default_rng(seed)
    critical = t.ppf(1-alpha, n_treatment+n_control-2)
    rejected = 0
    batch = 2_000
    for start in range(0, REPLICATES, batch):
        count = min(batch, REPLICATES-start)
        treatment = rng.normal(difference, sd, (count, n_treatment))
        control = rng.normal(0, sd, (count, n_control))
        estimated = treatment.mean(1)-control.mean(1)
        pooled = (((treatment-treatment.mean(1)[:,None])**2).sum(1)+((control-control.mean(1)[:,None])**2).sum(1))/(n_treatment+n_control-2)
        se = np.sqrt(pooled*(1/n_treatment+1/n_control))
        rejected += int(np.sum(((estimated+margin)/se > critical) & ((estimated-margin)/se < -critical)))
    estimate = rejected/REPLICATES
    mcse = math.sqrt(estimate*(1-estimate)/REPLICATES)
    tolerance = max(.01, 3*mcse)
    return {"seed": seed, "replicates": REPLICATES, "estimate": estimate, "exact_power": exact_power,
            "mcse": mcse, "confidence_interval_95": [estimate-1.96*mcse, estimate+1.96*mcse],
            "tolerance": tolerance, "acceptance_rule": "abs(simulated-exact) <= max(0.01, 3*MCSE)",
            "status": "PASS" if abs(estimate-exact_power) <= tolerance else "FAIL"}


def _monotonicity(engine):
    base = {"expected_difference": .1, "sd": 1, "equivalence_margin": .5, "allocation_ratio": 1, "alpha": .05, "power": .8, "dropout_rate": 0}
    def total(**updates): return _agent(engine, "sample_size", {**base, **updates}).analysis_required_sample_size
    values = {"base": total(), "narrower_margin": total(equivalence_margin=.4), "larger_sd": total(sd=1.2),
              "closer_to_margin": total(expected_difference=.3), "higher_power": total(power=.9), "smaller_alpha": total(alpha=.025)}
    checks = {name: value >= values["base"] for name, value in values.items() if name != "base"}
    return {"status": "PASS" if all(checks.values()) else "FAIL", "sample_sizes": values, "checks": checks}


def _dropout(engine):
    base = {"expected_difference": .1, "sd": 1, "equivalence_margin": .5, "allocation_ratio": 2, "alpha": .05, "power": .8}
    rows = {str(d): _agent(engine, "sample_size", {**base, "dropout_rate": d}) for d in (0, .1, .2)}
    analyzable = [x.analysis_required_sample_size for x in rows.values()]
    randomized = [x.randomized_sample_size for x in rows.values()]
    passed = len(set(analyzable)) == 1 and randomized == sorted(randomized)
    return {"status": "PASS" if passed else "FAIL", "analyzable_totals": analyzable, "randomized_totals": randomized}


def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def run(write=False):
    environment = probe()
    rscript = environment["rscript"].get("selected")
    if not rscript: raise RuntimeError("ENVIRONMENT_BLOCKED: Rscript unavailable")
    package = _probe_package(rscript, "PowerTOST", ["power.TOST"])
    if package.get("status") != "FOUND" or package.get("version") != "1.5.7" or not package.get("functions", {}).get("power.TOST"):
        raise RuntimeError("DEPENDENCY_BLOCKED: exact PowerTOST 1.5.7 power.TOST unavailable")
    engine = CountingEngine(rscript)
    document = yaml.safe_load(FIXTURES.read_text(encoding="utf-8"))
    fixtures = {item["id"]: _validate_fixture(engine, item) for item in document["cases"]}
    monotonicity = _monotonicity(engine)
    dropout = _dropout(engine)
    simulations = {}
    for offset, fixture_id in enumerate(("eq_centered_sample", "eq_k2_repaired", "eq_khalf_repaired")):
        row = fixtures[fixture_id]; inputs = row["clinical_inputs"]; groups = row["analyzable"]["groups"]
        simulations[fixture_id] = _simulation(n_treatment=groups["treatment"], n_control=groups["control"], difference=inputs["expected_difference"], sd=inputs["sd"], margin=inputs["equivalence_margin"], alpha=inputs["alpha"], exact_power=row["achieved_power"], seed=SEED+offset)
    gates = {
        "direct_package_reproduction": "PASS" if all(x["direct_package"]["status"] == "PASS" for x in fixtures.values()) else "FAIL",
        "independent_exact_reference": "PASS" if all(x["independent_exact_integral"]["status"] == "PASS" for x in fixtures.values()) else "FAIL",
        "search_minimality": "PASS" if all(x["minimality"]["status"] == "PASS" for x in fixtures.values()) else "FAIL",
        "allocation_dropout_rounding": "PASS" if dropout["status"] == "PASS" and all(x["dropout_and_result_contract"] == "PASS" for x in fixtures.values()) else "FAIL",
        "edge_cases_monotonicity": monotonicity["status"],
        "simulation": "PASS" if all(x["status"] == "PASS" for x in simulations.values()) else "FAIL",
        "reproducibility_versions": "PASS",
    }
    passed = all(value == "PASS" for value in gates.values()) and all(x["status"] == "PASS" for x in fixtures.values())
    old_paths = [ROOT/"sample_size/validation/round5_fixed_design_evidence.json", ROOT/"sample_size/validation/benchmarks/round5_fixed_design.yaml", ROOT/"sample_size/validation/round42_evidence.json"]
    evidence = {"schema_version": 1, "benchmark_id": BENCHMARK_ID, "benchmark_status": "FROZEN_VALIDATED" if passed else "VALIDATION_FAILED",
        "validation_date": str(date.today()), "basis_commit": subprocess.run(["git","rev-parse","HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip(),
        "environment": {"Python": platform.python_version(), "SciPy": scipy.__version__, "R": environment["r"], "PowerTOST": package, "rscript": rscript},
        "live_execution": {"subprocess_executions": engine.executions, "successful": engine.successes, "failed": engine.failures,
                           "authoritative_power_tost_calls": engine.authoritative_calls},
        "fixtures": fixtures, "monotonicity": monotonicity, "dropout": dropout, "simulations": simulations, "validation_gates": gates,
        "failure_classification": None if passed else "IMPLEMENTATION_DEFECT", "final_status": "BENCHMARK_VALIDATED" if passed else "IMPLEMENTED_UNVALIDATED",
        "preserved_evidence_sha256": {str(path.relative_to(ROOT)).replace('\\','/'): _sha(path) for path in old_paths}}
    if write:
        EVIDENCE.write_text(json.dumps(evidence, indent=2)+"\n", encoding="utf-8")
        document["status"] = evidence["benchmark_status"]
        for item in document["cases"]:
            row = fixtures[item["id"]]
            item.update({"validation_status": "FROZEN_VALIDATED" if row["status"] == "PASS" and passed else "VALIDATION_PENDING",
                         "exact_package_arguments": row["exact_package_arguments"], "analyzable": row["analyzable"], "randomized": row["randomized"],
                         "achieved_power": row["achieved_power"], "preceding_candidate_power": row["preceding_candidate_power"],
                         "independent_exact_integral": row["independent_exact_integral"], "spec_sha256": row["spec_sha256"],
                         "implementation_version": row["implementation_version"], "validation_gates": {k:v for k,v in gates.items()}})
        FIXTURES.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        summary = {"schema_version": 1, "validation_round": "5.3D", "benchmark_id": BENCHMARK_ID,
            "outcome": evidence["benchmark_status"], "final_status": evidence["final_status"], "environment": evidence["environment"],
            "fixtures": {"total": len(fixtures), "passed": sum(x["status"] == "PASS" for x in fixtures.values()), "failed": sum(x["status"] == "FAIL" for x in fixtures.values())},
            "validation_gates": gates, "simulation": {"seed_base": SEED, "replicates_per_scenario": REPLICATES, "results": simulations},
            "live_execution": evidence["live_execution"]}
        SUMMARY.write_text(yaml.safe_dump(summary, sort_keys=False), encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true")
    result = run(parser.parse_args().write)
    print(json.dumps({k: result[k] for k in ("benchmark_id","benchmark_status","environment","live_execution","validation_gates","final_status")}, indent=2))
