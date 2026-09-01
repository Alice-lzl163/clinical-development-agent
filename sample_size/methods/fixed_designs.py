import math

from sample_size.adapters import PwrAnovaAdapter, PwrTAdapter, PowerTOSTAdapter, TrialSizeProportionAdapter
from sample_size.agent.result import SampleSizeResult
from sample_size.engines.errors import PackageExecutionError, RequestValidationError


def _ceil_dropout(n: int, dropout: float) -> int:
    return math.ceil(n / (1 - dropout))


def _check_power(achieved: float, target: float):
    if achieved + 1e-10 < target:
        raise PackageExecutionError(f"forward achieved power {achieved} is below target {target} after upward rounding")


def _result(spec, values, adapter_result, *, solve_mode, analysis_total, randomized_total, per_group=None, per_sequence=None, derived=None, rounding=None, sidedness=None):
    raw = adapter_result.raw
    achieved = float(raw["achieved_power"])
    if solve_mode == "sample_size":
        _check_power(achieved, values["power"])
    package_warning = "Package version is recorded at runtime but no numerically validated exact version is pinned yet."
    return SampleSizeResult(
        method_id=spec["method_id"], test_key=spec["test_key"], solve_mode=solve_mode,
        analysis_required_sample_size=int(analysis_total) if analysis_total is not None else None, randomized_sample_size=int(randomized_total) if randomized_total is not None else None,
        sample_size_per_group=per_group, sample_size_per_sequence=per_sequence, required_events=None,
        target_power=float(values["power"]) if solve_mode == "sample_size" else None, achieved_power=achieved, alpha=float(values["alpha"]),
        sidedness=sidedness or spec["alpha"]["sidedness"], allocation={"contract": spec["allocation"], "realized": per_group or per_sequence},
        effect_parameters={key: value for key, value in values.items() if key not in {"alpha", "power", "dropout_rate", "allocation_ratio"}},
        derived_parameters=derived or {}, dropout_assumption=float(values["dropout_rate"]) if solve_mode == "sample_size" else None, rounding_applied=rounding or [],
        engine=spec["engine"]["engine_family"], runtime="R", package=spec["engine"]["package"],
        package_version=str(raw["package_version"]), function=adapter_result.function, package_arguments=adapter_result.package_arguments,
        warnings=list(spec["warnings"]) + list(raw.get("warnings", [])) + [package_warning], assumptions=list(spec["assumptions"]),
        validation_status="IMPLEMENTED_UNVALIDATED", reproducible_code=adapter_result.reproducible_code,
        r_version=str(raw["r_version"]), session_info=str(raw["session_info"]),
    )


class TTestMethod:
    def __init__(self, engine, test_key, test_type):
        self.adapter = PwrTAdapter(engine); self.test_key = test_key; self.test_type = test_type

    def calculate(self, spec, values, solve_mode):
        if self.test_key == "ttest_ind" and values["allocation_ratio"] != 1:
            raise RequestValidationError("ttest_ind frozen implementation requires allocation_ratio = 1")
        effect_name = "standardized_paired_effect" if self.test_key == "ttest_paired" else "standardized_effect"
        signed_effect = -values[effect_name] if values["alternative"] == "less" else values[effect_name]
        sided = "two_sided" if values["alternative"] == "two_sided" else "one_sided"
        if solve_mode == "sample_size":
            result = self.adapter.calculate(effect=signed_effect, alpha=values["alpha"], power=values["power"], alternative=values["alternative"], test_type=self.test_type)
            n = int(result.raw["analysis_n"]); randomized = _ceil_dropout(n, values["dropout_rate"])
        else:
            n_name = {"ttest_one":"analyzable_sample_size","ttest_paired":"analyzable_pairs","ttest_ind":"analyzable_sample_size_per_arm"}[self.test_key]
            n = values[n_name]; randomized = None
            result = self.adapter.power(n=n, effect=signed_effect, alpha=values["alpha"], alternative=values["alternative"], test_type=self.test_type)
        if self.test_key == "ttest_ind":
            return _result(spec, values, result, solve_mode=solve_mode, analysis_total=2*n, randomized_total=2*randomized if randomized is not None else None, per_group={"treatment": n, "control": n}, derived={"signed_standardized_effect": signed_effect,"analyzable_per_arm": n, "randomized_per_arm": randomized}, rounding=["ceil package n per arm", "ceil dropout inflation per arm"] if solve_mode=="sample_size" else [], sidedness=sided)
        if self.test_key == "ttest_paired":
            return _result(spec, values, result, solve_mode=solve_mode, analysis_total=n, randomized_total=randomized, per_sequence={"complete_pairs_or_participants": n}, derived={"signed_standardized_effect": signed_effect,"complete_analyzable_pairs": n, "randomized_participants": randomized}, rounding=["ceil package complete-pair n", "ceil dropout inflation"] if solve_mode=="sample_size" else [], sidedness=sided)
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=n, randomized_total=randomized, per_group={"one_sample": n}, derived={"signed_standardized_effect": signed_effect,"analyzable_subjects": n, "randomized_subjects": randomized}, rounding=["ceil package n", "ceil dropout inflation"] if solve_mode=="sample_size" else [], sidedness=sided)


class AnovaMethod:
    def __init__(self, engine): self.adapter = PwrAnovaAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        groups = values["groups"]
        if solve_mode == "sample_size":
            result = self.adapter.calculate(groups=groups, cohen_f=values["cohen_f"], alpha=values["alpha"], power=values["power"])
            per = int(result.raw["analysis_n_per_group"]); rand_per = _ceil_dropout(per, values["dropout_rate"])
        else:
            per=values["analyzable_sample_size_per_group"]; rand_per=None
            result=self.adapter.power(groups=groups,n_per_group=per,cohen_f=values["cohen_f"],alpha=values["alpha"])
        labels = {f"group_{i+1}": per for i in range(groups)}
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=groups*per, randomized_total=groups*rand_per if rand_per is not None else None, per_group=labels,
            derived={"analyzable_per_group": per, "analyzable_total": groups*per, "randomized_per_group": rand_per, "randomized_total": groups*rand_per if rand_per is not None else None},
            rounding=["ceil package n per group", "ceil dropout inflation per group"] if solve_mode=="sample_size" else [], sidedness="not_applicable")


class ProportionTwoMethod:
    def __init__(self, engine): self.adapter = TrialSizeProportionAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        if solve_mode=="sample_size":
            result = self.adapter.calculate(treatment_probability=values["treatment_probability"], control_probability=values["control_probability"], allocation_ratio=values["allocation_ratio"], alpha=values["alpha"], power=values["power"])
            nt,nc=int(result.raw["analysis_n_treatment"]),int(result.raw["analysis_n_control"]); rt,rc=_ceil_dropout(nt,values["dropout_rate"]),_ceil_dropout(nc,values["dropout_rate"])
        else:
            nt,nc=values["analyzable_treatment"],values["analyzable_control"]
            realized_ratio=nt/nc
            if not math.isclose(realized_ratio,values["allocation_ratio"],rel_tol=0,abs_tol=1e-12): raise RequestValidationError("analyzable_treatment / analyzable_control must equal allocation_ratio")
            result=self.adapter.power(treatment_probability=values["treatment_probability"],control_probability=values["control_probability"],n_treatment=nt,n_control=nc,alpha=values["alpha"]); rt=rc=None
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=nt+nc, randomized_total=rt+rc if rt is not None else None, per_group={"treatment": nt, "control": nc},
            derived={"beta": 1-values["power"] if solve_mode=="sample_size" else None, "analyzable_treatment": nt, "analyzable_control": nc, "randomized_treatment": rt, "randomized_control": rc},
            rounding=["ceil TrialSize treatment n", "ceil implied control n", "ceil dropout inflation per arm"] if solve_mode=="sample_size" else [], sidedness=spec["alpha"]["sidedness"])


class BioequivalenceMethod:
    def __init__(self, engine): self.adapter = PowerTOSTAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        if solve_mode=="sample_size":
            result=self.adapter.calculate(cv=values["cv"],theta0=values["theta0"],lower_limit=values["lower_limit"],upper_limit=values["upper_limit"],design=values["design"],alpha=values["alpha"],power=values["power"])
            evaluable=int(result.raw["evaluable_total"]); inflated=_ceil_dropout(evaluable,values["dropout_rate"]); randomized=math.ceil(inflated/2)*2; half=randomized//2
            realized={"TR":half,"RT":half} if values["design"]=="2x2" else {"treatment":half,"control":half}
        else:
            evaluable=values["evaluable_total"]; randomized=None; half=evaluable//2
            result=self.adapter.power(n=evaluable,cv=values["cv"],theta0=values["theta0"],lower_limit=values["lower_limit"],upper_limit=values["upper_limit"],design=values["design"],alpha=values["alpha"])
            realized={"TR":half,"RT":half} if values["design"]=="2x2" else {"treatment":half,"control":half}
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=evaluable, randomized_total=randomized, per_group=realized if values["design"]=="parallel" else None, per_sequence=realized if values["design"]=="2x2" else None,
            derived={"evaluable_total":evaluable,"randomization_block_size":2,"randomized_total":randomized,"randomized_per_sequence_or_arm":half},
            rounding=["PowerTOST evaluable total","ceil dropout inflation","ceil to two-subject randomization block"] if solve_mode=="sample_size" else [],sidedness="two_one_sided_tests")
