"""Compare independently generated platform evidence using frozen tolerances."""

import argparse
import json
from pathlib import Path


INTEGER_FIELDS = ("analysis_required_sample_size", "randomized_sample_size")
FLOAT_FIELDS = ("achieved_power",)


def compare(paths):
    documents = [(Path(path).parent.name, json.loads(Path(path).read_text(encoding="utf-8"))) for path in paths]
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
            if not left or not right: continue
            for field in INTEGER_FIELDS:
                if left[field] != right[field]: discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": field, "classification": "operating-system numerical difference", "baseline": left[field], "observed": right[field]})
            if left.get("sample_size_per_group") != right.get("sample_size_per_group") or left.get("sample_size_per_sequence") != right.get("sample_size_per_sequence"):
                discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": "group_or_sequence_sizes", "classification": "operating-system numerical difference"})
            for field in FLOAT_FIELDS:
                difference = abs(left[field] - right[field])
                if difference > 1e-6: discrepancies.append({"platform": platform_name, "fixture": fixture_id, "field": field, "classification": "operating-system numerical difference", "absolute_difference": difference})
    return {"baseline": baseline_name, "platform_count": len(documents), "fixture_count": len(baseline["fixtures"]), "tolerances": {"integer": "exact", "achieved_power_absolute": 1e-6}, "status": "PASS" if not discrepancies else "FAIL", "discrepancies": discrepancies}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("evidence", nargs="+"); parser.add_argument("--output", required=True); args = parser.parse_args()
    result = compare(args.evidence)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(0 if result["status"] == "PASS" else 1)
