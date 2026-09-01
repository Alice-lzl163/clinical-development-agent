from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SampleSizeResult:
    method_id: str
    test_key: str
    solve_mode: str
    analysis_required_sample_size: int
    randomized_sample_size: int
    sample_size_per_group: dict[str, int] | None
    sample_size_per_sequence: dict[str, int] | None
    required_events: int | None
    target_power: float
    achieved_power: float
    alpha: float
    sidedness: str
    allocation: dict[str, Any]
    effect_parameters: dict[str, Any]
    derived_parameters: dict[str, Any]
    dropout_assumption: float
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
