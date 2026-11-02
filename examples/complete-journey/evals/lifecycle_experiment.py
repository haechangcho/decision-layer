"""Persistent-workspace B/C lifecycle experiment. Raw data stays outside Git.

Run init once, then author/business for phases 1..3, then audit. A fresh Codex
session handles each job, while each arm keeps its code, documents and history.
No automatic successful-result selection or hidden business-call retries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import time

import httpx
import jwt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = [1, 2, 3, 4, 5, 6, 9, 12, 5, 12]
MODEL = "gpt-6.1-sol"
SEED = 20261028
BRIEF = """You are the organization's analyst, authoring a reusable procedure for
nontechnical business owners who ask short campaign-performance questions.
Implement the attached analytical specification without changing provider-owned
definitions. No campaign-specific numerical answers or special-case branches.
Keep analytical knowledge in the published assets, not in future user questions.
Retain previous versions and evidence. This is authoring, not a business analysis.
Do not read benchmark oracle files, other experiment arms, or repository evals.
Only semantic metadata may be queried in authoring. Use synthetic fixtures for tests.
"""


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def hashes(work):
    return {str(p.relative_to(work)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(work.rglob("*")) if p.is_file() and not p.is_symlink()
            and "history" not in p.relative_to(work).parts
            and p.suffix in {".py", ".md", ".yaml", ".yml", ".toml"}}


def schedule():
    result = []
    rng = random.Random(SEED)
    for phase in (1, 2, 3):
        cases = list(enumerate(CASES, 1))
        rng.shuffle(cases)
        for slot, campaign in cases:
            arms = ["B", "C"]
            rng.shuffle(arms)
            question = (f"{campaign}번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘."
                        if slot <= 8 else f"{campaign}번 캠페인 다시 검토해줘. 다음에도 할 만했는지 근거를 알려줘.")
            for arm in arms:
                result.append(dict(phase=phase, slot=slot, campaign=campaign, arm=arm, question=question))
    return result


def env_for(work, api_url):
    env = os.environ.copy()
    env.update(BENCH_CUBE_URL="http://127.0.0.1:4100/cubejs-api/v1", BENCH_EXPORT_DIR=str(work),
               DL_API_URL=api_url, PATH=f"{ROOT / '.venv/bin'}{os.pathsep}{env.get('PATH', '')}")
    env["BENCH_CUBE_TOKEN"] = jwt.encode({"sub": "lifecycle", "exp": int(time.time()) + 3600},
        env.get("BENCH_CUBE_SECRET", "local-quickstart-secret-change-me-0123456789"), algorithm="HS256")
    return env


def prompt_for(kind, arm, phase, question=""):
    if kind == "author":
        change = {1: "Publish procedure version 1: minimum 30 observations per group; no confidence interval.",
                  2: "Publish version 2: organization policy now requires at least 100 observations in EACH target group for adjusted estimation. Keep descriptives, but refuse the adjusted estimate below that limit. This is an operational policy, not a universal statistical rule. Update all current executable assets and documentation; preserve old evidence.",
                  3: "Publish version 3: retain the 100-per-group policy and add HC3 heteroskedasticity-robust 95% normal confidence intervals (statsmodels cov_type='HC3', use_t=False) for the same target coefficient. Keep identical covariates and point estimator. Do not compute intervals for refused cohorts. Update calculation, validation, explanations and current version references."}[phase]
        target = ("Publish campaign-playbook.md as the current analyst document, with a clear version and change history. "
                  + ("In this initial document-only condition, author prose only: do not prebuild analytical Python. Future business sessions may create and retain code from your document."
                     if phase == 1 else "Inspect the Python previously generated in this workspace. You MAY update and test reusable code as well as the document; do not force downstream users to recreate it. Keep the current entry point discoverable.")
                  if arm == "B" else
                  "Author a working Decision Layer project in project/ with registered Python Methods and one published discoverable campaign Recipe. Use separate cohort and adjusted-estimation steps so a policy refusal preserves cohort diagnostics. Use ordinary python_method/DataInput, require_complete=True and unique observation IDs. Version changed Methods and the Recipe, preserving previous versions outside the active registry if necessary. The current Recipe must route to current Method versions. Read reference/ for publicly downloaded framework docs. Do NOT read or print local repository source files or installed Decision Layer source code; these are not authorized for transmission. You may consult public GitHub documentation at https://github.com/haechangcho/decision-layer. Calling the installed framework and inspecting signatures without source text is allowed. Run decision-layer check --project project and synthetic pytest tests before finishing. Do not start a server.")
        return BRIEF + "\nRead specification.md.\n" + change + "\n" + target + "\nPython: " + str(ROOT / ".venv/bin/python")
    access = ("Use only the cube MCP for source data. Read campaign-playbook.md for the current organizational procedure. You may write, edit, run and reuse Python in this workspace using " + str(ROOT / ".venv/bin/python") + ". Existing scripts and history persist across requests. Do not access Decision Layer or another arm."
              if arm == "B" else "Use decision_layer MCP and the current published registered analysis assets. Do not write analytical code. Prior results and your workspace history may be inspected. Do not access the document-only arm.")
    if kind == "audit":
        return access + "\nDo not obtain new source data or execute a new analysis for this audit. Inspect retained history and artifacts.\nQuestion: 2번 캠페인을 처음 검토했을 때와 지금 결론이 달라졌다면 왜 달라졌어? 당시 결과와 현재 결과, 각 절차 버전, 바뀐 기준과 근거 기록을 찾아 설명해줘."
    return (access + "\nFor this new request, obtain current source data through the tools; code may be reused but do not substitute an old answer or old data file. Retain calculation/query evidence and the procedure version used in this workspace. Provide a concise Korean business answer with material limitations.\nQuestion: " + question)


def run_job(base, kind, arm, phase, job_id, question="", campaign=None):
    work = base / arm
    output = base / "jobs" / job_id
    output.mkdir(parents=True, exist_ok=False)
    before = hashes(work)
    prompt = prompt_for(kind, arm, phase, question)
    runtime_bin = base / "frozen-runtime/bin"
    if runtime_bin.is_dir():
        prompt = prompt.replace(str(ROOT / ".venv/bin/python"), str(runtime_bin / "python"))
        prompt += "\nUse the frozen-runtime Python specified above for all framework calls; do not use a historical interpreter path from older documents."
    (output / "prompt.txt").write_text(prompt)
    server = "decision_layer" if arm == "C" and kind != "author" else "cube"
    cfg = ({"command": str(ROOT / ".venv/bin/decision-layer-mcp"), "args": [], "env_vars": ["DL_API_URL"], "startup_timeout_sec": 60}
           if server == "decision_layer" else
           {"command": str(ROOT / ".venv/bin/python"), "args": [str(HERE / "cube_baseline.py")],
            "env_vars": ["BENCH_CUBE_URL", "BENCH_CUBE_TOKEN", "BENCH_EXPORT_DIR"], "startup_timeout_sec": 60})
    if runtime_bin.is_dir():
        cfg["command"] = str(runtime_bin / ("decision-layer-mcp" if server == "decision_layer" else "python"))
    table = "{ " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in cfg.items()) + " }"
    cmd = ["codex", "exec", "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--json", "--approve-for-me",
           "-c", f"mcp_servers.{server}={table}", "-c", 'model_reasoning_effort="medium"',
           "-C", str(work), "--model", MODEL, prompt]
    start = time.monotonic()
    environment = env_for(work, "http://127.0.0.1:8130")
    if runtime_bin.is_dir():
        environment["PYTHONPATH"] = str(base / "frozen-runtime/src")
        environment["PATH"] = str(runtime_bin) + os.pathsep + environment["PATH"]
    print(json.dumps({"event": "starting", "job": job_id}), flush=True)
    with (output / "events.jsonl").open("w") as stdout, (output / "stderr.log").open("w") as stderr:
        try:
            process = subprocess.run(cmd, cwd=work, env=environment, stdout=stdout,
                                     stderr=stderr, stdin=subprocess.DEVNULL, text=True, timeout=900 if kind == "author" else 600)
            code = process.returncode
        except subprocess.TimeoutExpired:
            code = -1
    elapsed = time.monotonic() - start
    events = []
    for line in (output / "events.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    items = [e["item"] for e in events if e.get("type") == "item.completed"]
    messages = [x.get("text", "") for x in items if x.get("type") == "agent_message"]
    usage = next((e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None)
    after = hashes(work)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    result = dict(job_id=job_id, kind=kind, arm=arm, phase=phase, campaign=campaign, question=question,
                  model_requested=MODEL, effort="medium", exit_code=code, seconds=round(elapsed, 3), usage=usage,
                  answer=messages[-1] if messages else None, changed_files=changed,
                  mcp_calls=[{k: x.get(k) for k in ("tool", "arguments", "status")} for x in items if x.get("type") == "mcp_tool_call"])
    dump(output / "summary.json", result)
    dump(output / "hashes.json", {"before": before, "after": after})
    # Preserve the exact procedure/code revision used, independently of future edits.
    for relative in after:
        target = output / "assets" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(work / relative, target)
    history = work / "history" / job_id
    history.mkdir(parents=True)
    shutil.copyfile(output / "summary.json", history / "summary.json")
    shutil.copyfile(output / "events.jsonl", history / "events.jsonl")
    print(json.dumps({k: result[k] for k in ("job_id", "exit_code", "seconds", "usage", "changed_files")}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "author", "business", "audit"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--arm", choices=["B", "C"])
    args = parser.parse_args()
    base = args.output
    if args.action == "init":
        base.mkdir(parents=True, exist_ok=False)
        for arm in ("B", "C"):
            work = base / arm
            work.mkdir()
            shutil.copyfile(HERE / "campaign-playbook.md", work / "specification.md")
        reference = base / "C/reference"
        reference.mkdir()
        for name in ("docs/reference/method-contract.md", "docs/guides/method-projects.md", "docs/guides/recipes.md"):
            url = "https://raw.githubusercontent.com/haechangcho/decision-layer/main/" + name
            response = httpx.get(url, follow_redirects=True, timeout=60)
            response.raise_for_status()
            (reference / Path(name).name).write_text(response.text)
        dump(base / "freeze.json", {"created_at_unix": time.time(), "model": MODEL, "seed": SEED,
                                   "schedule": schedule(), "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                   "cli": subprocess.check_output(["codex", "--version"], text=True).strip()})
    elif args.action == "business":
        frozen = json.loads((base / "freeze.json").read_text())
        for cell in frozen["schedule"]:
            if cell["phase"] != args.phase or (args.arm and cell["arm"] != args.arm):
                continue
            job_id = f"p{args.phase}-q{cell['slot']:02d}-c{cell['campaign']}-{cell['arm']}"
            # Resume only completed jobs, including failures; never select retries.
            if (base / "jobs" / job_id / "summary.json").exists():
                continue
            run_job(base, "business", cell["arm"], args.phase, job_id, cell["question"], cell["campaign"])
    else:
        for arm in ([args.arm] if args.arm else ["B", "C"]):
            run_job(base, args.action, arm, args.phase, f"p{args.phase}-{args.action}-{arm}")


if __name__ == "__main__":
    main()
