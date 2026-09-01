from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SampleSizeResult:
    method_id: str
    test_key: str
    solve_mode: str
    analysis_required_sample_size: int | None
    randomized_sample_size: int | None
    sample_size_per_group: dict[str, int] | None
    sample_size_per_sequence: dict[str, int] | None
    required_events: int | None
    target_power: float | None
    achieved_power: float
    alpha: float
    sidedness: str
    allocation: dict[str, Any]
    effect_parameters: dict[str, Any]
    derived_parameters: dict[str, Any]
    dropout_assumption: float | None
    rounding_applied: list[str]
    engine: str
    runtime: str
    package: str
    package_version: str
    function: str
    package_arguments: dict[str, Any]
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    validation_status: str = "IMPLEMENTED_UNVALIDATED"
    reproducible_code: str = ""
    r_version: str = ""
    session_info: str = ""
    specification_version: str = "1"
    implementation_version: str = "round-4.3"
    benchmark_id: str = "fixed-design-round4-v1"
    validation_environment: str = "UNVALIDATED_VERSION"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_protocol_dict(self) -> dict[str, Any]:
        """Return the stable downstream contract without adding narrative claims."""
        randomized_groups = None
        labels = self.sample_size_per_group or self.sample_size_per_sequence
        if labels and self.randomized_sample_size is not None:
            if "randomized_treatment" in self.derived_parameters:
                randomized_groups = {"treatment": self.derived_parameters["randomized_treatment"], "control": self.derived_parameters["randomized_control"]}
            else:
                per = self.derived_parameters.get("randomized_per_arm", self.derived_parameters.get("randomized_per_group", self.derived_parameters.get("randomized_per_sequence_or_arm")))
                if per is not None: randomized_groups = {name: per for name in labels}
                elif len(labels) == 1: randomized_groups = {next(iter(labels)): self.randomized_sample_size}
        return {
            "statistical_result": {
                "analyzable_sample_size": self.analysis_required_sample_size,
                "group_specific_sample_sizes": self.sample_size_per_group or self.sample_size_per_sequence,
                "total_analyzable_n": self.analysis_required_sample_size,
                "achieved_power": self.achieved_power,
                "target_power": self.target_power,
                "alpha": self.alpha,
            },
            "operational_adjustment": {
                "dropout_rate": self.dropout_assumption,
                "randomized_group_sizes": randomized_groups,
                "randomized_total_n": self.randomized_sample_size,
                "rounding_block_rules": self.rounding_applied,
            },
            "method_metadata": {
                "test_key": self.test_key, "method_id": self.method_id,
                "authoritative_engine": self.engine, "runtime": self.runtime,
                "package": self.package, "function": self.function,
                "statistical_specification_version": self.specification_version,
                "implementation_version": self.implementation_version,
            },
            "validation_metadata": {
                "numerical_validation_status": self.validation_status,
                "validated_environment_match": self.validation_environment,
                "benchmark_id": self.benchmark_id,
                "package_version": self.package_version, "r_version": self.r_version,
            },
            "interpretation": {
                "assumptions": self.assumptions, "warnings": self.warnings,
                "unsupported_extrapolations": [],
                "effect_assumptions": self.effect_parameters,
            },
            "reproducibility": {
                "derived_parameters": self.derived_parameters,
                "package_arguments": self.package_arguments,
                "exact_r_code": self.reproducible_code,
            },
        }
