import hashlib
import json
import math

from sample_size.adapters import (
    PowerTOSTAdapter,
    PwrAnovaAdapter,
    PwrProportionAdapter,
    PwrTAdapter,
    TrialSizeMcNemarAdapter,
    TrialSizeMeanEquivalenceAdapter,
    TrialSizeProportionAdapter,
    TrialSizeProportionMarginAdapter,
)
from sample_size.agent.result import SampleSizeResult
from sample_size.engines.errors import PackageExecutionError, RequestValidationError
from sample_size.validation.dependency_compatibility import classify_runtime


_VALIDATED_PACKAGE_VERSIONS = {"pwr": "1.3.0", "TrialSize": "1.4.1", "PowerTOST": "1.5.7"}


def _ceil_dropout(n: int, dropout: float) -> int:
    return math.ceil(n / (1 - dropout))


def _check_power(achieved: float, target: float):
    if achieved + 1e-10 < target:
        raise PackageExecutionError(f"forward achieved power {achieved} is below target {target} after upward rounding")


def _result(spec, values, adapter_result, *, solve_mode, analysis_total, randomized_total, per_group=None, per_sequence=None, derived=None, rounding=None, sidedness=None, benchmark_eligible=True, implementation_version="round-4.3", benchmark_id="fixed-design-round4-v1"):
    raw = adapter_result.raw
    achieved = float(raw["achieved_power"])
    if not math.isfinite(achieved) or not 0 <= achieved <= 1:
        raise PackageExecutionError("R engine returned an invalid achieved power")
    if analysis_total is not None and (not isinstance(analysis_total, int) or analysis_total <= 0):
        raise PackageExecutionError("R engine returned a nonsensical analyzable sample size")
    if randomized_total is not None and (not isinstance(randomized_total, int) or randomized_total <= 0):
        raise PackageExecutionError("operational adjustment produced a nonsensical randomized sample size")
    if solve_mode == "sample_size":
        _check_power(achieved, values["power"])
    package = spec["engine"]["package"]
    package_version = str(raw["package_version"])
    r_version = str(raw["r_version"])
    validation_environment = classify_runtime(package, package_version, r_version)
    if validation_environment == "INCOMPATIBLE_VERSION":
        raise PackageExecutionError(f"{package} {package_version} is empirically incompatible with this calculator runtime")
    version_qualified = validation_environment in {"MATCHED_VALIDATED_ENVIRONMENT", "TESTED_COMPATIBLE_VERSION"}
    validation_status = "BENCHMARK_VALIDATED" if benchmark_eligible and version_qualified else "IMPLEMENTED_UNVALIDATED"
    version_warnings = [] if version_qualified else [
        f"Runtime versions differ from the validated R 4.6.1 / {package} "
        f"{_VALIDATED_PACKAGE_VERSIONS.get(package)} environment; numerical validation status is not inherited."
    ]
    validation_warnings = [] if benchmark_eligible else [
        "This Round 5.2A calculator is implemented but has not completed numerical benchmark validation."
    ]
    return SampleSizeResult(
        method_id=spec["method_id"], test_key=spec["test_key"], solve_mode=solve_mode,
        analysis_required_sample_size=int(analysis_total) if analysis_total is not None else None, randomized_sample_size=int(randomized_total) if randomized_total is not None else None,
        sample_size_per_group=per_group, sample_size_per_sequence=per_sequence, required_events=None,
        target_power=float(values["power"]) if solve_mode == "sample_size" else None, achieved_power=achieved, alpha=float(values["alpha"]),
        sidedness=sidedness or spec["alpha"]["sidedness"], allocation={"contract": spec["allocation"], "realized": per_group or per_sequence},
        effect_parameters={key: value for key, value in values.items() if key not in {"alpha", "power", "dropout_rate", "allocation_ratio"}},
        derived_parameters=derived or {}, dropout_assumption=float(values["dropout_rate"]) if solve_mode == "sample_size" else None, rounding_applied=rounding or [],
        engine=spec["engine"]["engine_family"], runtime="R", package=package,
        package_version=package_version, function=adapter_result.function, package_arguments=adapter_result.package_arguments,
        warnings=list(spec["warnings"]) + list(raw.get("warnings", [])) + version_warnings + validation_warnings, assumptions=list(spec["assumptions"]),
        validation_status=validation_status, reproducible_code=adapter_result.reproducible_code,
        r_version=r_version, session_info=str(raw["session_info"]),
        validation_environment=validation_environment,
        specification_version="sha256:" + hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        implementation_version=implementation_version, benchmark_id=benchmark_id,
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
            allocation_deviation=abs(nt-values["allocation_ratio"]*nc)
            if allocation_deviation>1+1e-12: raise RequestValidationError("analyzable arm sizes are inconsistent with allocation_ratio beyond the frozen one-subject rounding allowance")
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


class ProportionOneMethod:
    def __init__(self, engine): self.adapter = PwrProportionAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        effect = self.adapter.cohen_h(values["alternative_probability"], values["null_probability"])
        sided = "two_sided" if values["alternative"] == "two_sided" else "one_sided"
        if solve_mode == "sample_size":
            result = self.adapter.calculate(alternative_probability=values["alternative_probability"], null_probability=values["null_probability"], alpha=values["alpha"], power=values["power"], alternative=values["alternative"])
            n = int(result.raw["analysis_n"]); randomized = _ceil_dropout(n, values["dropout_rate"])
        else:
            n = values["analyzable_sample_size"]; randomized = None
            result = self.adapter.power(n=n, alternative_probability=values["alternative_probability"], null_probability=values["null_probability"], alpha=values["alpha"], alternative=values["alternative"])
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=n, randomized_total=randomized, per_group={"one_sample": n},
            derived={"signed_cohen_h": effect, "analyzable_subjects": n, "randomized_subjects": randomized},
            rounding=["ceil package n", "ceil dropout inflation"] if solve_mode == "sample_size" else [], sidedness=sided,
            benchmark_eligible=False, implementation_version="round-5.2a", benchmark_id="not_assigned")


class ProportionPairedMethod:
    def __init__(self, engine): self.adapter = TrialSizeMcNemarAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        result = self.adapter.calculate(p_treatment_only=values["p_treatment_only"], p_control_only=values["p_control_only"], alpha=values["alpha"], power=values["power"])
        n = int(result.raw["analysis_n"]); randomized = _ceil_dropout(n, values["dropout_rate"])
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=n, randomized_total=randomized, per_sequence={"complete_matched_pairs": n},
            derived={"beta": 1-values["power"], "discordance_ratio": values["p_treatment_only"]/values["p_control_only"], "total_discordance_probability": values["p_treatment_only"]+values["p_control_only"], "complete_analyzable_pairs": n, "randomized_pairs": randomized},
            rounding=["ceil TrialSize complete-pair n", "ceil dropout inflation"], sidedness="two_sided",
            benchmark_eligible=False, implementation_version="round-5.2a", benchmark_id="not_assigned")


class MeanEquivalenceMethod:
    def __init__(self, engine): self.adapter = TrialSizeMeanEquivalenceAdapter(engine)
    def calculate(self, spec, values, solve_mode):
        result = self.adapter.calculate(expected_difference=values["expected_difference"], sd=values["sd"], equivalence_margin=values["equivalence_margin"], allocation_ratio=values["allocation_ratio"], alpha=values["alpha"], power=values["power"])
        nt, nc = int(result.raw["analysis_n_treatment"]), int(result.raw["analysis_n_control"])
        rt, rc = _ceil_dropout(nt, values["dropout_rate"]), _ceil_dropout(nc, values["dropout_rate"])
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=nt+nc, randomized_total=rt+rc, per_group={"treatment": nt, "control": nc},
            derived={"beta": 1-values["power"], "analyzable_treatment": nt, "analyzable_control": nc, "randomized_treatment": rt, "randomized_control": rc},
            rounding=["ceil TrialSize treatment n", "ceil implied control n", "ceil dropout inflation per arm"], sidedness="two_one_sided_tests",
            benchmark_eligible=False, implementation_version="round-5.2a", benchmark_id="not_assigned")


class ProportionMarginMethod:
    def __init__(self, engine, test_key): self.adapter = TrialSizeProportionMarginAdapter(engine); self.test_key = test_key
    def calculate(self, spec, values, solve_mode):
        delta = values["treatment_probability"] - values["control_probability"]
        margin = -values["noninferiority_margin"] if self.test_key == "non_inferiority" else values["superiority_margin"]
        result = self.adapter.calculate(treatment_probability=values["treatment_probability"], control_probability=values["control_probability"], allocation_ratio=values["allocation_ratio"], margin=margin, alpha=values["alpha"], power=values["power"])
        nt, nc = int(result.raw["analysis_n_treatment"]), int(result.raw["analysis_n_control"])
        rt, rc = _ceil_dropout(nt, values["dropout_rate"]), _ceil_dropout(nc, values["dropout_rate"])
        return _result(spec, values, result, solve_mode=solve_mode, analysis_total=nt+nc, randomized_total=rt+rc, per_group={"treatment": nt, "control": nc},
            derived={"beta": 1-values["power"], "expected_risk_difference": delta, "package_margin": margin, "analyzable_treatment": nt, "analyzable_control": nc, "randomized_treatment": rt, "randomized_control": rc},
            rounding=["ceil TrialSize treatment n", "ceil implied control n", "ceil dropout inflation per arm"], sidedness="one_sided",
            benchmark_eligible=False, implementation_version="round-5.2a", benchmark_id="not_assigned")
