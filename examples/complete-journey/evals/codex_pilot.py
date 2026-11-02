"""Two-condition Codex pilot against the local Complete Journey demo.

Writes raw transcripts under /private/tmp. These are diagnostic, not verified
benchmark results; review them for sensitive values before publishing.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import jwt

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SALES_PROCEDURE = ("Compare total retailer receipts and units over July and August 2001. For every department, "
             "calculate August minus July, using zero for an absent group only after complete retrieval. "
             "Select the department with the largest absolute change, preserving its sign. If tied, ask "
             "the user rather than choosing. Compare the selected department's brand types for both "
             "periods and compare that department's units. Describe whether units and receipts move in the same direction; "
             "if not, say the divergence needs further investigation, without assuming a price effect. "
             "Give both totals, department and brand values, evidence, and limitations. "
             "Receipts are not profit; changes do not establish causality.")
CAMPAIGN_PROCEDURE = ("For campaign 8, compare eligible targeted and non-targeted households using the "
    "ordinary least squares method. Use post-campaign 30-day household sales as outcome, target-list "
    "membership as treatment, and prior 30-day sales and purchase frequency as covariates. "
    "The campaign started 2001-02-15 in the example calendar. Report the adjusted coefficient, "
    "number of observations, evidence and limitations. Treatment is not random; identification is "
    "unverified, so describe association only, not a causal campaign effect.")
QUESTIONS = {"sales": "예제 달력 기준 2001년 7월과 8월의 수취액과 수량 변화를 조사해줘.",
             "campaign": "8번 캠페인의 대상 여부와 이후 30일 구매금액의 관계를 이전 구매 이력을 고려해 비교해줘.",
             "business8": "8번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘.",
             "business7": "7번 캠페인 성과가 어땠어? 다음 캠페인을 진행할지 판단하는 데 도움이 될 근거를 알려줘."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="Explicit model ID; omit only for a diagnostic run")
    prompt_source = parser.add_mutually_exclusive_group(required=True)
    prompt_source.add_argument("--task", choices=list(QUESTIONS))
    prompt_source.add_argument("--question", help="Business question without an analytical procedure")
    parser.add_argument("--condition", choices=["cube", "cube_playbook", "decision_layer"], help="Optional diagnostic rerun of one condition")
    parser.add_argument("--playbook", type=Path, help="Analyst prose for the optional cube_playbook condition")
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/dl-codex-pilot"))
    args = parser.parse_args()
    if args.condition == "cube_playbook" and not args.playbook:
        parser.error("cube_playbook requires --playbook")
    playbook = args.playbook.read_text() if args.playbook else None
    question = args.question or QUESTIONS[args.task]
    args.output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env["BENCH_CUBE_URL"] = env.get("BENCH_CUBE_URL", "http://127.0.0.1:4100/cubejs-api/v1")
    env["BENCH_CUBE_TOKEN"] = jwt.encode({"sub": "benchmark", "exp": int(time.time()) + 3600},
        env.get("BENCH_CUBE_SECRET", "local-quickstart-secret-change-me-0123456789"), algorithm="HS256")
    env["DL_API_URL"] = env.get("DL_API_URL", "http://127.0.0.1:8127")
    env["PATH"] = f"{ROOT / '.venv/bin'}{os.pathsep}{env.get('PATH', '')}"
    business = bool(args.question) or args.task.startswith("business")
    procedure = "" if business else (SALES_PROCEDURE if args.task == "sales" else CAMPAIGN_PROCEDURE)
    recipe = "benchmark-receipts-change" if args.task == "sales" else "benchmark-campaign-8-ols"
    decision_instruction = ("Use the decision_layer MCP to investigate the question. "
                            "Use registered analysis assets as appropriate, and record evidence. Do not write analytical code.") if business else (
        f"Use the decision_layer MCP tools. Find and execute the saved {recipe} Recipe if it matches the supplied procedure. Record the Run. Do not write analytical code.")
    cases = {
        "cube": (str(ROOT / ".venv/bin/python"), [str(HERE / "cube_baseline.py")], ["BENCH_CUBE_URL", "BENCH_CUBE_TOKEN", "BENCH_EXPORT_DIR"],
                 "Use only the cube MCP tools to obtain data. You may write and run Python using installed libraries "
                 f"in the working directory. Use {ROOT / '.venv/bin/python'} for Python. "
                 "For a large result, export_query_csv saves a Cube query to that directory. "
                 "Do not use Decision Layer code, prewritten analysis tools, or access other data sources."),
        "decision_layer": (str(ROOT / ".venv/bin/decision-layer-mcp"), [], ["DL_API_URL"],
                           decision_instruction),
    }
    if playbook is not None:
        command, tool_args, env_vars, instruction = cases["cube"]
        cases["cube_playbook"] = (command, tool_args, env_vars, instruction +
            " Read campaign-playbook.md in the working directory for the organization's analytical procedure.")
    for name, (command, tool_args, env_vars, instruction) in cases.items():
        if args.condition and name != args.condition:
            continue
        config = {"command": command, "args": tool_args, "env_vars": env_vars, "startup_timeout_sec": 60}
        table = "{ " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in config.items()) + " }"
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="dl-codex-pilot-") as work:
            env["BENCH_EXPORT_DIR"] = work
            if name == "cube_playbook":
                (Path(work) / "campaign-playbook.md").write_text(playbook)
            server_name = "cube" if name == "cube_playbook" else name
            cmd = ["codex", "exec", "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--json", "--approve-for-me",
                   "-c", f"mcp_servers.{server_name}={table}", "-c", 'model_reasoning_effort="medium"', "-C", work]
            if args.model:
                cmd += ["--model", args.model]
            prompt = f"{instruction}\n{procedure}\nQuestion: {question}"
            (args.output / f"{name}-prompt.txt").write_text(prompt)
            cmd += [prompt]
            try:
                result = subprocess.run(cmd, cwd=work, env=env, text=True, capture_output=True, timeout=600, stdin=subprocess.DEVNULL)
                stdout, stderr, code = result.stdout, result.stderr, result.returncode
            except subprocess.TimeoutExpired as exc:
                stdout = (exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr, code = "timeout after 600 seconds", -1
            # Preserve the generated code and its local inputs/outputs for review.
            # These may contain raw data and must not be published unreviewed.
            artifacts = [path for path in Path(work).rglob("*") if path.is_file() and not path.is_symlink()
                         and path.suffix in {".py", ".csv", ".json", ".txt"} and path.stat().st_size <= 20_000_000]
            if artifacts:
                destination = args.output / f"{name}-workspace"
                destination.mkdir(exist_ok=True)
                for path in artifacts:
                    target = destination / path.relative_to(work)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        (args.output / f"{name}.jsonl").write_text(stdout)
        (args.output / f"{name}.stderr").write_text(stderr)
        events = [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]
        calls = [e.get("item", {}) for e in events if e.get("type") == "item.completed" and e.get("item", {}).get("type") == "mcp_tool_call"]
        usage = next((e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None)
        messages = [e["item"].get("text", "") for e in events if e.get("item", {}).get("type") == "agent_message"]
        summary = {"condition": name, "question": question, "model_requested": args.model, "reasoning_effort": "medium", "exit_code": code, "seconds": round(time.monotonic()-start, 2),
                   "calls": [{"server": x.get("server"), "tool": x.get("tool"), "status": x.get("status")} for x in calls],
                   "usage": usage, "answer": messages[-1] if messages else None}
        (args.output / f"{name}-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
