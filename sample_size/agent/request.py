from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SampleSizeRequest:
    test_key: str
    parameters: Mapping[str, Any]
    solve_mode: str = "sample_size"

    @classmethod
    def from_value(cls, value: "SampleSizeRequest | Mapping[str, Any]") -> "SampleSizeRequest":
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise TypeError("request must be a SampleSizeRequest or mapping")
        allowed = {"test_key", "solve_mode", "parameters"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown request fields: {sorted(unknown)}")
        return cls(test_key=value.get("test_key"), solve_mode=value.get("solve_mode", "sample_size"), parameters=value.get("parameters", {}))
