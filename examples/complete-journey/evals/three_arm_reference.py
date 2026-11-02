"""Independent numeric check of the exposed cohort, never sent to the agent.

Uses the same provider-owned cohort view; does not independently validate its
construction from original source CSVs. No Decision Layer Method is imported.
"""
import argparse
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    query = """COPY (SELECT campaign_id, observation_id, is_targeted::int AS targeted,
      pre_sales_30d, pre_baskets_30d, post_sales_30d, age_code, income_code,
      composition_code, overlapping_campaigns FROM journey.campaign_household_outcomes
      WHERE eligible AND campaign_id IN ('10','11') ORDER BY campaign_id, observation_id)
      TO STDOUT WITH CSV HEADER"""
    result = subprocess.run(["docker", "exec", "decision-layer-demo-db382e2fca68-postgres-1",
                             "psql", "-U", "demo_loader", "-d", "journey", "-c", query],
                            capture_output=True, text=True, check=True)
    frame = pd.read_csv(io.StringIO(result.stdout))
    reference = {}
    for campaign, data in frame.groupby("campaign_id"):
        x = np.column_stack([np.ones(len(data)), data[["targeted", "pre_sales_30d", "pre_baskets_30d"]]])
        beta, _, rank, _ = np.linalg.lstsq(x, data.post_sales_30d, rcond=None)
        groups = []
        for target, part in data.groupby("targeted"):
            groups.append({"targeted": int(target), "n": len(part),
                           "pre_sales": float(part.pre_sales_30d.mean()),
                           "pre_frequency": float(part.pre_baskets_30d.mean()),
                           "post_sales": float(part.post_sales_30d.mean()),
                           "overlap_n": int((part.overlapping_campaigns > 0).sum()),
                           "missing": {name: int(part[name].isna().sum()) for name in
                                       ["age_code", "income_code", "composition_code"]}})
        reference[str(campaign)] = {"n": len(data), "rank": int(rank), "groups": groups,
                                    "intercept": float(beta[0]), "target_coefficient": float(beta[1]),
                                    "pre_sales_coefficient": float(beta[2]),
                                    "pre_frequency_coefficient": float(beta[3])}
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "cohort.csv").write_text(result.stdout)
    (args.output / "reference.json").write_text(json.dumps(reference, indent=2))
    (args.output / "query.sql").write_text(query)
    print(json.dumps(reference, indent=2))


if __name__ == "__main__":
    main()
