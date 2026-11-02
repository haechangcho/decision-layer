"""Summarize reviewed observations; this script does not grade answers itself."""
import argparse
import json
from pathlib import Path
from statistics import mean

ARMS = ("cube", "cube_playbook", "decision_layer")
VALIDITY = ("V1", "V2", "V3", "V4", "V5")


def summarize(observations):
    result = {}
    for arm in ARMS:
        rows = [row for row in observations if row["condition"] == arm]
        if not rows:
            raise ValueError(f"No reviewed observations for {arm}")
        result[arm] = {
            "n": len(rows),
            "valid": sum(all(row["review"][k] == "pass" for k in VALIDITY) for row in rows),
            "unknown": sum(any(row["review"][k] == "unknown" for k in VALIDITY) for row in rows),
            "mean_seconds": mean(row["seconds"] for row in rows),
            "input_tokens": sum(row["usage"]["input_tokens"] for row in rows),
            "cached_input_tokens": sum(row["usage"]["cached_input_tokens"] for row in rows),
            "uncached_input_tokens": sum(row["usage"]["input_tokens"] - row["usage"]["cached_input_tokens"] for row in rows),
            "output_tokens": sum(row["usage"]["output_tokens"] for row in rows),
            "charge_usd": None,
        }
    cases = sorted({row["case_id"] for row in observations})
    case_scores = {}
    for case in cases:
        case_scores[case] = {}
        for arm in ARMS:
            rows = [r for r in observations if r["case_id"] == case and r["condition"] == arm]
            if not rows:
                raise ValueError(f"Missing pair: {case}/{arm}")
            case_scores[case][arm] = mean(all(r["review"][k] == "pass" for k in VALIDITY) for r in rows)
    return {"arms": result, "case_count": len(cases), "case_scores": case_scores,
            "paired_valid_rate_difference_C_minus_B": mean(s["decision_layer"] - s["cube_playbook"] for s in case_scores.values()),
            "inference": "Diagnostic descriptive results; no significance claim or cost claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observations", type=Path)
    args = parser.parse_args()
    data = json.loads(args.observations.read_text())
    print(json.dumps(summarize(data["observations"]), indent=2))


if __name__ == "__main__":
    main()
