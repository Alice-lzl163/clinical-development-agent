from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from sample_size.engines.errors import PackageContractError, RequestValidationError, UnsupportedSolveModeError

SPEC_DIR = Path(__file__).resolve().parents[1] / "specs"
with (SPEC_DIR / "schema.json").open(encoding="utf-8") as stream:
    _SCHEMA = yaml.safe_load(stream)
_SPEC_VALIDATOR = Draft202012Validator(_SCHEMA)


def load_frozen_spec(test_key: str) -> dict[str, Any]:
    if not isinstance(test_key, str) or not test_key:
        raise RequestValidationError("test_key must be a non-empty string")
    path = SPEC_DIR / f"{test_key}.yaml"
    if not path.is_file():
        raise RequestValidationError(f"unknown test_key: {test_key!r}")
    with path.open(encoding="utf-8") as stream:
        spec = yaml.safe_load(stream)
    errors = sorted(_SPEC_VALIDATOR.iter_errors(spec), key=lambda error: list(error.path))
    if errors:
        raise PackageContractError(f"invalid specification {test_key}: {errors[0].message}")
    if spec["specification_status"] != "SPEC_FROZEN":
        raise PackageContractError(f"method is not SPEC_FROZEN: {test_key}")
    return spec


def validate_request(spec: dict[str, Any], solve_mode: str, parameters: Any) -> dict[str, Any]:
    if solve_mode not in spec["solve_modes"] or not spec["solve_modes"].get(solve_mode):
        raise UnsupportedSolveModeError(f"solve mode {solve_mode!r} is not enabled by {spec['test_key']}")
    if solve_mode != "sample_size":
        raise UnsupportedSolveModeError(
            f"{spec['test_key']} declares {solve_mode!r}, but its frozen clinical-input contract has no forward-solve sample-size input; refusing to infer one"
        )
    if not isinstance(parameters, dict):
        raise RequestValidationError("parameters must be an object")
    contracts = {item["name"]: item for item in spec["inputs"]}
    unknown = set(parameters) - set(contracts)
    if unknown:
        raise RequestValidationError(f"unknown clinical parameters: {sorted(unknown)}")
    missing = [name for name, item in contracts.items() if item["required"] and name not in parameters]
    if missing:
        raise RequestValidationError(f"missing required clinical parameters: {missing}")
    values = dict(parameters)
    for name, item in contracts.items():
        if name not in values and item["default"] is not None:
            values[name] = item["default"]
        if name not in values:
            continue
        value = values[name]
        expected = item["type"]
        valid_type = {
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "string": isinstance(value, str), "boolean": isinstance(value, bool),
            "array": isinstance(value, list), "object": isinstance(value, dict),
        }[expected]
        if not valid_type:
            raise RequestValidationError(f"{name} must have type {expected}")
        limits = item["valid_range"] or {}
        if "minimum" in limits and value < limits["minimum"]: raise RequestValidationError(f"{name} is below minimum")
        if "maximum" in limits and value > limits["maximum"]: raise RequestValidationError(f"{name} exceeds maximum")
        if "exclusive_minimum" in limits and value <= limits["exclusive_minimum"]: raise RequestValidationError(f"{name} must exceed exclusive minimum")
        if "exclusive_maximum" in limits and value >= limits["exclusive_maximum"]: raise RequestValidationError(f"{name} must be below exclusive maximum")
        if "allowed_values" in limits and value not in limits["allowed_values"]: raise RequestValidationError(f"{name} must be one of {limits['allowed_values']}")
    if spec["test_key"] == "be_tost" and not (values["lower_limit"] < values["theta0"] < values["upper_limit"]):
        raise RequestValidationError("bioequivalence requires lower_limit < theta0 < upper_limit")
    if spec["test_key"] == "proportion_two" and values["treatment_probability"] == values["control_probability"]:
        raise RequestValidationError("treatment and control probabilities must differ for sample-size inversion")
    return values
