"""Independent lifecycle numerical oracle and cost accounting (not agent input)."""
import argparse
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


def numeric_reference(data):
    """OLS and HC3 sandwich calculated independently of registered Methods."""
    x = np.column_stack([np.ones(len(data)), data[["targeted", "pre_sales_30d", "pre_baskets_30d"]]])
    y = data.post_sales_30d.to_numpy()
    beta, _, rank, _ = np.linalg.lstsq(x, y, rcond=None)
    bread = np.linalg.inv(x.T @ x)
    hat = np.einsum("ij,jk,ik->i", x, bread, x)
    residual = y - x @ beta
    meat = x.T @ (x * ((residual / (1 - hat)) ** 2)[:, None])
    se = np.sqrt(np.diag(bread @ meat @ bread))
    groups = []
    for targeted, part in data.groupby("targeted"):
        groups.append({"targeted": int(targeted), "n": len(part),
                       "pre_sales": float(part.pre_sales_30d.mean()),
                       "pre_frequency": float(part.pre_baskets_30d.mean()),
                       "post_sales": float(part.post_sales_30d.mean()),
                       "overlap_n": int((part.overlapping_campaigns > 0).sum()),
                       "missing": {name: int(part[name].isna().sum()) for name in
                                   ("age_code", "income_code", "composition_code")}})
    return {"n": len(data), "rank": int(rank), "groups": groups,
            "target_coefficient": float(beta[1]), "hc3_se": float(se[1]),
            "hc3_ci95_normal": [float(beta[1] - 1.959963984540054 * se[1]),
                                float(beta[1] + 1.959963984540054 * se[1])],
            "eligible": {"1": min(g["n"] for g in groups) >= 30,
                         "2": min(g["n"] for g in groups) >= 100,
                         "3": min(g["n"] for g in groups) >= 100}}


def totals(rows):
    usage = [r.get("usage") for r in rows]
    known = [u for u in usage if u is not None]
    return {"jobs": len(rows), "failed_processes": sum(r["exit_code"] != 0 for r in rows),
            "seconds": round(sum(r["seconds"] for r in rows), 3),
            "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 3) if rows else None,
            "usage_missing_jobs": len(usage) - len(known),
            "reported_input_tokens": sum(u.get("input_tokens", 0) for u in known),
            "reported_cached_input_tokens": sum(u.get("cached_input_tokens", 0) for u in known),
            "reported_uncached_input_tokens": sum(u.get("input_tokens", 0) - u.get("cached_input_tokens", 0) for u in known),
            "reported_output_tokens": sum(u.get("output_tokens", 0) for u in known)}


def aggregate(rows):
    return {arm: {"total": totals([r for r in rows if r["arm"] == arm]),
                  "initial_authoring": totals([r for r in rows if r["arm"] == arm and r["kind"] == "author" and r["phase"] == 1]),
                  "maintenance": totals([r for r in rows if r["arm"] == arm and r["kind"] == "author" and r["phase"] > 1]),
                  "by_kind": {kind: totals([r for r in rows if r["arm"] == arm and r["kind"] == kind])
                              for kind in sorted({r["kind"] for r in rows})},
                  "business_by_phase": {str(phase): totals([r for r in rows if r["arm"] == arm and r["kind"] == "business" and r["phase"] == phase])
                                        for phase in (1, 2, 3)}} for arm in ("B", "C")}


def sensitivity(rows, reviews):
    """Descriptive paired exclusions; never replace the full observed totals."""
    business = [r for r in rows if r["kind"] == "business"]
    affected = {r["job_id"].rsplit("-", 1)[0] for r in business
                if reviews.get(r["job_id"], {}).get("adapter_confounds")}
    return {"adapter_affected_pairs": sorted(affected),
            "business_excluding_adapter_pairs": {
                arm: totals([r for r in business if r["arm"] == arm and r["job_id"].rsplit("-", 1)[0] not in affected])
                for arm in ("B", "C")},
            "isolated_runtime_business_phases_2_3": {
                arm: totals([r for r in business if r["arm"] == arm and r["phase"] in (2, 3)])
                for arm in ("B", "C")}}


def reviewed_observations(base):
    """Refuse to turn a partial study or unreviewed result into a full report."""
    rows = [json.loads(p.read_text()) for p in sorted((base / "jobs").glob("*/summary.json"))]
    reviews = json.loads((base / "manual-reviews.json").read_text())
    for arm in ("B", "C"):
        for phase in (1, 2, 3):
            business = [r for r in rows if r["arm"] == arm and r["phase"] == phase and r["kind"] == "business"]
            if len(business) != 10:
                raise ValueError(f"Incomplete phase {phase}, arm {arm}: {len(business)}/10")
            if not any(r["kind"] == "author" and r["arm"] == arm and r["phase"] == phase for r in rows):
                raise ValueError("Missing author/maintenance cost")
        if not any(r["kind"] == "audit" and r["arm"] == arm for r in rows):
            raise ValueError("Missing retrospective audit")
    for row in rows:
        if row["kind"] in {"business", "audit"} and row["job_id"] not in reviews:
            raise ValueError(f"Unreviewed answer: {row['job_id']}")
    fields = ("job_id", "kind", "arm", "phase", "campaign", "question", "model_requested", "effort", "exit_code", "seconds", "usage", "answer")
    provenance = {name: json.loads((base / name).read_text())
                  for name in ("freeze.json", "source-freeze.json", "runtime-isolation.json", "after.json")
                  if (base / name).exists()}
    return {"raw_directory": str(base), "provenance": provenance,
            "costs": aggregate(rows), "sensitivity": sensitivity(rows, reviews),
            "jobs": [{**{k: r.get(k) for k in fields},
                      "mcp_call_count": len(r.get("mcp_calls", [])),
                      "changed_source_file_count": len(r.get("changed_files", [])),
                      "review": reviews.get(r["job_id"])} for r in rows]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["reference", "aggregate", "reviewed"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "reference":
        query = """COPY (SELECT campaign_id, observation_id, is_targeted::int AS targeted,
          pre_sales_30d, pre_baskets_30d, post_sales_30d, age_code, income_code,
          composition_code, overlapping_campaigns FROM journey.campaign_household_outcomes
          WHERE eligible AND campaign_id IN ('1','2','3','4','5','6','9','12')
          ORDER BY campaign_id, observation_id) TO STDOUT WITH CSV HEADER"""
        result = subprocess.run(["docker", "exec", "decision-layer-demo-db382e2fca68-postgres-1",
                                 "psql", "-U", "demo_loader", "-d", "journey", "-c", query],
                                capture_output=True, text=True, check=True)
        frame = pd.read_csv(io.StringIO(result.stdout))
        reference = {str(k): numeric_reference(data) for k, data in frame.groupby("campaign_id")}
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "query.sql").write_text(query)
        (args.output / "cohort.csv").write_text(result.stdout)
        (args.output / "reference.json").write_text(json.dumps(reference, indent=2))
        print(json.dumps(reference, indent=2))
    elif args.action == "reviewed":
        result = reviewed_observations(args.output)
        destination = Path(__file__).with_name("lifecycle-observations-2026-10-27.json")
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(destination)
    else:
        rows = [json.loads(p.read_text()) for p in sorted((args.output / "jobs").glob("*/summary.json"))]
        result = aggregate(rows)
        (args.output / "costs.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
