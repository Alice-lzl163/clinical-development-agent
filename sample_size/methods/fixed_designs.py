import math

from sample_size.adapters import PwrAnovaAdapter, PwrTAdapter, PowerTOSTAdapter, TrialSizeProportionAdapter
from sample_size.agent.result import SampleSizeResult
from sample_size.engines.errors import PackageContractError, PackageExecutionError, RequestValidationError


def _ceil_dropout(n: int, dropout: float) -> int:
    return math.ceil(n / (1 - dropout))


def _check_power(achieved: float, target: float):
    if achieved + 1e-10 < target:
        raise PackageExecutionError(f"forward achieved power {achieved} is below target {target} after upward rounding")


def _result(spec, values, adapter_result, *, analysis_total, randomized_total, per_group=None, per_sequence=None, derived=None, rounding=None, sidedness=None):
    raw = adapter_result.raw
    achieved = float(raw["achieved_power"])
    _check_power(achieved, values["power"])
    package_warning = "Package version is recorded at runtime but no numerically validated exact version is pinned yet."
    return SampleSizeResult(
        method_id=spec["method_id"], test_key=spec["test_key"], solve_mode="sample_size",
        analysis_required_sample_size=int(analysis_total), randomized_sample_size=int(randomized_total),
        sample_size_per_group=per_group, sample_size_per_sequence=per_sequence, required_events=None,
        target_power=float(values["power"]), achieved_power=achieved, alpha=float(values["alpha"]),
        sidedness=sidedness or spec["alpha"]["sidedness"], allocation={"contract": spec["allocation"], "realized": per_group or per_sequence},
        effect_parameters={key: value for key, value in values.items() if key not in {"alpha", "power", "dropout_rate", "allocation_ratio"}},
        derived_parameters=derived or {}, dropout_assumption=float(values["dropout_rate"]), rounding_applied=rounding or [],
        engine=spec["engine"]["engine_family"], runtime="R", package=spec["engine"]["package"],
        package_version=str(raw["package_version"]), function=spec["engine"]["function"], package_arguments=adapter_result.package_arguments,
        warnings=list(spec["warnings"]) + list(raw.get("warnings", [])) + [package_warning], assumptions=list(spec["assumptions"]),
        validation_status="IMPLEMENTED_UNVALIDATED", reproducible_code=adapter_result.reproducible_code,
        r_version=str(raw["r_version"]), session_info=str(raw["session_info"]),
    )


class TTestMethod:
    def __init__(self, engine, test_key, test_type):
        self.adapter = PwrTAdapter(engine); self.test_key = test_key; self.test_type = test_type

    def calculate(self, spec, values):
        if self.test_key == "ttest_ind" and values["allocation_ratio"] != 1:
            raise RequestValidationError("ttest_ind frozen implementation requires allocation_ratio = 1")
        effect_name = "standardized_paired_effect" if self.test_key == "ttest_paired" else "standardized_effect"
        if values["alternative"] == "less" and values[effect_name] > 0:
            raise PackageContractError(
                f"{self.test_key} frozen contract permits only a positive standardized effect but maps it unchanged to pwr with alternative='less'; refusing to infer a negative sign"
            )
        result = self.adapter.calculate(effect=values[effect_name], alpha=values["alpha"], power=values["power"], alternative=values["alternative"], test_type=self.test_type)
        n = int(result.raw["analysis_n"]); randomized = _ceil_dropout(n, values["dropout_rate"])
        sided = "two_sided" if values["alternative"] == "two_sided" else "one_sided"
        if self.test_key == "ttest_ind":
            return _result(spec, values, result, analysis_total=2*n, randomized_total=2*randomized, per_group={"treatment": n, "control": n}, derived={"analyzable_per_arm": n, "randomized_per_arm": randomized}, rounding=["ceil package n per arm", "ceil dropout inflation per arm"], sidedness=sided)
        if self.test_key == "ttest_paired":
            return _result(spec, values, result, analysis_total=n, randomized_total=randomized, per_sequence={"complete_pairs_or_participants": n}, derived={"complete_analyzable_pairs": n, "randomized_participants": randomized}, rounding=["ceil package complete-pair n", "ceil dropout inflation"], sidedness=sided)
        return _result(spec, values, result, analysis_total=n, randomized_total=randomized, per_group={"one_sample": n}, derived={"analyzable_subjects": n, "randomized_subjects": randomized}, rounding=["ceil package n", "ceil dropout inflation"], sidedness=sided)


class AnovaMethod:
    def __init__(self, engine): self.adapter = PwrAnovaAdapter(engine)
    def calculate(self, spec, values):
        result = self.adapter.calculate(groups=values["groups"], cohen_f=values["cohen_f"], alpha=values["alpha"], power=values["power"])
        per = int(result.raw["analysis_n_per_group"]); rand_per = _ceil_dropout(per, values["dropout_rate"]); groups = values["groups"]
        labels = {f"group_{i+1}": per for i in range(groups)}
        return _result(spec, values, result, analysis_total=groups*per, randomized_total=groups*rand_per, per_group=labels,
            derived={"analyzable_per_group": per, "analyzable_total": groups*per, "randomized_per_group": rand_per, "randomized_total": groups*rand_per},
            rounding=["ceil package n per group", "ceil dropout inflation per group"], sidedness="not_applicable")


class ProportionTwoMethod:
    def __init__(self, engine): self.adapter = TrialSizeProportionAdapter(engine)
    def calculate(self, spec, values):
        result = self.adapter.calculate(treatment_probability=values["treatment_probability"], control_probability=values["control_probability"], allocation_ratio=values["allocation_ratio"], alpha=values["alpha"], power=values["power"])
        nt, nc = int(result.raw["analysis_n_treatment"]), int(result.raw["analysis_n_control"])
        rt, rc = _ceil_dropout(nt, values["dropout_rate"]), _ceil_dropout(nc, values["dropout_rate"])
        return _result(spec, values, result, analysis_total=nt+nc, randomized_total=rt+rc, per_group={"treatment": nt, "control": nc},
            derived={"beta": 1-values["power"], "analyzable_treatment": nt, "analyzable_control": nc, "randomized_treatment": rt, "randomized_control": rc},
            rounding=["ceil TrialSize treatment n", "ceil implied control n", "ceil dropout inflation per arm"], sidedness=spec["alpha"]["sidedness"])


class BioequivalenceMethod:
    def __init__(self, engine): self.adapter = PowerTOSTAdapter(engine)
    def calculate(self, spec, values):
        result = self.adapter.calculate(cv=values["cv"], theta0=values["theta0"], lower_limit=values["lower_limit"], upper_limit=values["upper_limit"], design=values["design"], alpha=values["alpha"], power=values["power"])
        evaluable = int(result.raw["evaluable_total"]); inflated = _ceil_dropout(evaluable, values["dropout_rate"]); randomized = math.ceil(inflated/2)*2; half = randomized//2
        realized = {"TR": half, "RT": half} if values["design"] == "2x2" else {"treatment": half, "control": half}
        return _result(spec, values, result, analysis_total=evaluable, randomized_total=randomized, per_group=realized if values["design"] == "parallel" else None, per_sequence=realized if values["design"] == "2x2" else None,
            derived={"evaluable_total": evaluable, "randomization_block_size": 2, "randomized_total": randomized, "randomized_per_sequence_or_arm": half},
            rounding=["PowerTOST evaluable total", "ceil dropout inflation", "ceil to two-subject randomization block"], sidedness="two_one_sided_tests")
