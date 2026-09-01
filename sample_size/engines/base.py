from abc import ABC, abstractmethod
from typing import Any


class ExecutionEngine(ABC):
    @abstractmethod
    def execute(self, *, package: str, function: str, calculation_code: str) -> dict[str, Any]:
        raise NotImplementedError
