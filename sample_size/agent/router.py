from typing import Any, Mapping

from sample_size.engines.r_engine import RExecutionEngine
from sample_size.engines.errors import UnknownMethodError
from sample_size.registry.method_registry import IMPLEMENTED_KEYS, get_method

from .request import SampleSizeRequest
from .result import SampleSizeResult
from .validation import load_frozen_spec, validate_request


def calculate_sample_size(request: SampleSizeRequest | Mapping[str, Any], *, engine: RExecutionEngine | None = None) -> SampleSizeResult:
    """Execute a frozen local calculator; numerical values always originate in R."""
    parsed = SampleSizeRequest.from_value(request)
    if parsed.test_key not in IMPLEMENTED_KEYS:
        raise UnknownMethodError(f"test_key is not implemented in the authorized local calculator set: {parsed.test_key!r}")
    spec = load_frozen_spec(parsed.test_key)
    values = validate_request(spec, parsed.solve_mode, dict(parsed.parameters))
    execution_engine = engine or RExecutionEngine()
    method = get_method(parsed.test_key, execution_engine)
    return method.calculate(spec, values, parsed.solve_mode)
