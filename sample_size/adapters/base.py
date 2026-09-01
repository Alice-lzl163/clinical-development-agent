import json
from dataclasses import dataclass
from typing import Any

from sample_size.engines.r_engine import RExecutionEngine


def r_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (int, float)):
        return repr(value)
    raise TypeError(f"cannot encode R literal for {type(value).__name__}")


@dataclass(frozen=True)
class AdapterResult:
    raw: dict[str, Any]
    package_arguments: dict[str, Any]
    reproducible_code: str
    function: str


class PackageAdapter:
    package: str
    function: str

    def __init__(self, engine: RExecutionEngine):
        self.engine = engine
