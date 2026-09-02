"""Compare independently generated platform evidence using frozen tolerances."""

import argparse
import json
from pathlib import Path


INTEGER_FIELDS = ("analysis_required_sample_size", "randomized_sample_size")
DERIVED_INTEGER_FIELDS = ("analyzable_treatment", "analyzable_control", "analyzable_total", "randomized_treatment", "randomized_control", "randomized_total", "complete_analyzable_pairs", "randomized_pairs")
FLOAT_FIELDS = ("achieved_power",)
REQUIRED_DOCUMENT_FIELDS = ("environment", "live_execution", "fixtures", "method_gates")


def _platform_name(path):
    name = Path(path).parent.name
    return name.removeprefix("sample-size-runtime-")


def _load(path):
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed or unreadable evidence: {path}") from exc
    if not isinstance(document, dict) or any(field not in document for field in REQUIRED_DOCUMENT_FIELDS):
        raise ValueError(f"evidence is missing required document fields: {path}")
    if not isinstance(document["fixtures"], dict) or not document["fixtures"]:
        raise ValueError(f"evidence has no fixture results: {path}")
    return document


def _validate_fixture(fixture_id, result, path):
    if not isinstance(result, dict) or "status" not in result:
        raise ValueError(f"fixture {fixture_id} is missing status in {path}")
    agent = result.get("agent_result")
    if agent is None:
        return None
    required = (*INTEGER_FIELDS, *FLOAT_FIELDS, "sample_size_per_group", "sample_size_per_sequence", "benchmark_id", "rounding_applied", "derived_parameters")
    if not isinstance(agent, dict) or any(field not in agent for field in required):
        raise ValueError(f"fixture {fixture_id} is missing required comparison fields in {path}")
    return agent


def compare(paths, expected_platforms=None):
    if not paths:
        raise ValueError("no platform evidence files were supplied")
    documents = [(_platform_name(path), _load(path), path) for path in paths]
    names = [name for name, _, _ in documents]
    if len(names) != len(set(names)):
        raise ValueError("duplicate platform evidence was supplied")
    if expected_platforms is not None and set(names) != set(expected_platforms):
        raise ValueError(f"platform evidence mismatch: expected {sorted(expected_platforms)}, found {sorted(names)}")
    fixture_sets = {name: set(document["fixtures"]) for name, document, _ in documents}
    if len({frozenset(items) for items in fixture_sets.values()}) != 1:
        raise ValueError(f"fixture sets differ across platforms: {fixture_sets}")
    benchmark_ids = {}
    for name, document, path in documents:
        agents = [_validate_fixture(fixture_id, result, path) for fixture_id, result in document["fixtures"].items()]
        ids = {agent["benchmark_id"] for agent in agents if agent is not None}
        if not ids or None in ids:
            raise ValueError(f"evidence does not identify benchmark IDs for {name}")
        benchmark_ids[name] = tuple(sorted(ids))
    if len(set(benchmark_ids.values())) != 1:
        raise ValueError(f"benchmark IDs differ across platforms: {benchmark_ids}")
    documents = [(name, document) for name, document, _ in documents]
    baseline_name, baseline = documents[0]
    discrepancies = []
    for platform_name, document in documents[1:]:
        for fixture_id, expected in baseline["fixtures"].items():
            observed = document["fixtures"].get(fixture_id)
            if observed is None:
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "fixture", "classification": "operating-system numerical difference", "detail": "missing fixture"}); continue
            if expected["status"] != observed["status"]:
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "status", "classification": "operating-system numerical difference"}); continue
            left, right = expected.get("agent_result"), observed.get("agent_result")
            if (left is None) != (right is None):
                raise ValueError(f"required comparison fields differ for fixture {fixture_id}")
            if not left or not right: continue
            if left["benchmark_id"] != right["benchmark_id"]:
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "benchmark_id", "classification": "operating-system numerical difference", "baseline": left["benchmark_id"], "observed": right["benchmark_id"]})
            for field in INTEGER_FIELDS:
                if left[field] != right[field]: discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": field, "classification": "operating-system numerical difference", "baseline": left[field], "observed": right[field]})
            if left.get("sample_size_per_group") != right.get("sample_size_per_group") or left.get("sample_size_per_sequence") != right.get("sample_size_per_sequence"):
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "group_or_sequence_sizes", "classification": "operating-system numerical difference"})
            for field in FLOAT_FIELDS:
                difference = abs(left[field] - right[field])
                if difference > 1e-6: discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": field, "classification": "operating-system numerical difference", "absolute_difference": difference})
            if left.get("rounding_applied") != right.get("rounding_applied"):
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "rounding_applied", "classification": "operating-system numerical difference"})
            for field in DERIVED_INTEGER_FIELDS:
                lvalue, rvalue = left.get("derived_parameters", {}).get(field), right.get("derived_parameters", {}).get(field)
                if lvalue != rvalue:
                    discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": f"derived_parameters.{field}", "classification": "operating-system numerical difference", "baseline": lvalue, "observed": rvalue})
            derived_fields = set(left["derived_parameters"]) | set(right["derived_parameters"])
            for field in derived_fields-set(DERIVED_INTEGER_FIELDS):
                lvalue, rvalue = left["derived_parameters"].get(field), right["derived_parameters"].get(field)
                if isinstance(lvalue, (int, float)) and not isinstance(lvalue, bool) and isinstance(rvalue, (int, float)) and not isinstance(rvalue, bool):
                    if abs(lvalue-rvalue) > 1e-6:
                        discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": f"derived_parameters.{field}", "classification": "operating-system numerical difference", "absolute_difference": abs(lvalue-rvalue)})
                elif lvalue != rvalue:
                    discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": f"derived_parameters.{field}", "classification": "operating-system numerical difference", "baseline": lvalue, "observed": rvalue})
    ids = next(iter(benchmark_ids.values()))
    return {"baseline": baseline_name, "platform_count": len(documents), "fixture_count": len(baseline["fixtures"]), "benchmark_id": ids[0] if len(ids) == 1 else None, "benchmark_ids": list(ids), "tolerances": {"integer": "exact", "achieved_power_absolute": 1e-6, "exposed_intermediate_absolute": 1e-6}, "status": "PASS" if not discrepancies else "FAIL", "discrepancies": discrepancies}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("evidence", nargs="+"); parser.add_argument("--expected-platform", action="append"); parser.add_argument("--output", required=True); args = parser.parse_args()
    result = compare(args.evidence, expected_platforms=args.expected_platform)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result["status"] == "PASS" else 1)
