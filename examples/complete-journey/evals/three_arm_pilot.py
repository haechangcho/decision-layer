"""Freeze and run the six-cell diagnostic; raw artifacts stay in a local folder."""
import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

import httpx
import jwt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TABLES = ("campaign_desc", "campaign_table", "coupon", "coupon_redempt",
          "hh_demographic", "household", "product", "transaction_data",
          "campaign_household_outcomes")


def source_hashes():
    files = list((ROOT / "src/decision_layer").rglob("*.py"))
    files += list((ROOT / "src/decision_layer/starters").rglob("*.md"))
    files += list((ROOT / "src/decision_layer/demo/assets/journey").rglob("*.yml"))
    files += [p for p in (HERE / "reuse-project").rglob("*")
              if p.suffix in {".py", ".yaml", ".md"}]
    files += [HERE / name for name in ("codex_pilot.py", "cube_baseline.py", "three_arm_pilot.py",
              "three-arm-cases.json", "three-arm-protocol.md", "campaign-playbook.md")]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(files))}


def snapshot(container, cube_url):
    sql = " UNION ALL ".join(
        f"SELECT '{table}', count(*), md5(string_agg(md5(row_to_json(t)::text), '' "
        f"ORDER BY md5(row_to_json(t)::text))) FROM journey.{table} t" for table in TABLES)
    # causal_data is a 36M-row promotion-placement table, not referenced by the
    # exposed Cube models. Only sources used by those models are fingerprinted.
    sql += " UNION ALL SELECT 'view:' || schemaname || '.' || viewname, 0, md5(definition) FROM pg_views WHERE schemaname='journey' ORDER BY 1"
    data = subprocess.run(["docker", "exec", container, "psql", "-U", "demo_loader", "-d", "journey",
                           "-At", "-c", sql], capture_output=True, text=True, check=True, timeout=180).stdout
    token = jwt.encode({"sub": "benchmark", "exp": int(time.time()) + 3600},
                       os.environ.get("BENCH_CUBE_SECRET", "local-quickstart-secret-change-me-0123456789"),
                       algorithm="HS256")
    response = httpx.get(cube_url.rstrip("/") + "/meta", headers={"Authorization": token}, timeout=60)
    response.raise_for_status()
    return {"tables": data.splitlines(), "excluded": ["causal_data: not referenced by exposed Cube models"], "catalog_sha256": hashlib.sha256(
        json.dumps(response.json(), sort_keys=True).encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:8129")
    parser.add_argument("--postgres-container", default="decision-layer-demo-db382e2fca68-postgres-1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["DL_API_URL"] = args.api_url
    cube_url = env.get("BENCH_CUBE_URL", "http://127.0.0.1:4100/cubejs-api/v1")
    response = httpx.get(args.api_url + "/recipes", timeout=30)
    response.raise_for_status()
    recipes = response.json()
    cases = json.loads((HERE / "three-arm-cases.json").read_text())
    plan = [{**case, "condition": arm} for case in cases
            for arm in ("cube", "cube_playbook", "decision_layer")]
    random.Random(20261027).shuffle(plan)
    frozen = {"created_at_unix": time.time(), "model_requested": args.model, "effort": "medium",
              "seed": 20261027, "plan": plan, "recipes": recipes, "source_sha256": source_hashes(),
              "versions": {name: version(name) for name in ("decision-layer", "pandas", "statsmodels", "numpy")},
              "cli": subprocess.check_output(["codex", "--version"], text=True).strip(),
              "data": snapshot(args.postgres_container, cube_url)}
    (args.output / "freeze.json").write_text(json.dumps(frozen, ensure_ascii=False, indent=2))
    print(json.dumps({"event": "frozen", "plan": plan}, ensure_ascii=False), flush=True)
    for index, cell in enumerate(plan, 1):
        if source_hashes() != frozen["source_sha256"]:
            raise RuntimeError("Frozen sources changed; do not mix revisions in an experiment")
        output = args.output / f"{index:02d}-{cell['id']}-{cell['condition']}"
        command = [sys.executable, str(HERE / "codex_pilot.py"), "--question", cell["question"],
                   "--condition", cell["condition"], "--model", args.model, "--output", str(output)]
        if cell["condition"] == "cube_playbook":
            command += ["--playbook", str(HERE / "campaign-playbook.md")]
        print(json.dumps({"event": "starting", "index": index, **cell}, ensure_ascii=False), flush=True)
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=660)
        (args.output / f"launcher-{index:02d}.log").write_text(result.stdout + "\n" + result.stderr)
        summary_path = output / f"{cell['condition']}-summary.json"
        summary = json.loads(summary_path.read_text()) if summary_path.exists() else {"exit_code": result.returncode}
        print(json.dumps({"event": "finished", "index": index, "exit_code": summary.get("exit_code"),
                          "seconds": summary.get("seconds"), "usage": summary.get("usage")}), flush=True)
    after = {"data": snapshot(args.postgres_container, cube_url), "source_sha256": source_hashes()}
    after["matches_freeze"] = after["data"] == frozen["data"] and after["source_sha256"] == frozen["source_sha256"]
    (args.output / "after.json").write_text(json.dumps(after, indent=2))
    print(json.dumps({"event": "complete", "matches_freeze": after["matches_freeze"]}), flush=True)


if __name__ == "__main__":
    main()
