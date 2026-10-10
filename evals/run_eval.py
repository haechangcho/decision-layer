"""End-to-end eval: a real model answers questions through the Decision Layer MCP server.

The model is driven through the Claude Code CLI (`claude -p`), so no API key is
needed — usage counts against the logged-in Claude Code account. Each run is a
fresh CLI process with built-in tools disabled and only the `decision-layer` MCP
server; the only tool guidance is the server's own instructions. Scenario
`user_replies` continue the same session with `--resume`.

    .venv/bin/python evals/run_eval.py examples/complete-journey/evals/scenarios.json [--repeats 3] [--only id …]

Needs a running Decision Layer API (DL_API_URL, default http://127.0.0.1:8000).

Scenario fields (all optional except id/question):
  must_call          Method names (query.drilldown) or recipes (recipe:<name>) that must be executed
  must_call_any      at least one of them
  expect_status      result statuses that must appear (success / needs_input / refused)
  must_ask_user      the first answer must ask the user something (needs_input handled correctly)
  user_replies       follow-up user turns
  expect_numbers     numbers the final answer must contain (±tolerance, default 0.01)
  must_mention       strings the answer must contain;  must_mention_any: at least one of them
  must_not_mention   strings the answer must not contain
  must_call_tools    MCP tool names required in the trace
  must_not_call      Methods/Recipes that must not execute
  require_single_run all execution calls must use one Run
  require_run_coverage completed Run must contain an outcome for each goal
  expect_goal_statuses outcome statuses that must occur
  must_use_recipe    exact Recipe reference required in the completed Run
Every run also checks numbers_grounded (each decimal number in the answers appears in some tool output) and
reports numbers_derivable (grounded, or a sum / difference / ratio of two tool-output numbers). Per scenario,
path_consistency is the share of repeats that executed the most common sequence of methods.

    --env KEY=VALUE   passed to the MCP server (e.g. DL_MCP_METHODS, DL_MCP_RULES)
    --label NAME      results go to <scenarios dir>/results/<timestamp>-<NAME>
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SERVER = "decision-layer"
PREFIX = f"mcp__{SERVER}__"
SYSTEM = "You are an analytics assistant answering data questions. Answer in the user's language."
RUN_TIMEOUT = 900
NUMBER = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d])")


# ── running ───────────────────────────────────────────────────────────────
async def claude(prompt: str, mcp_config: str, cwd: str, model: str | None, resume: str | None) -> list[dict]:
    cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--mcp-config", mcp_config, "--strict-mcp-config", "--tools", "",
           "--allowedTools", f"mcp__{SERVER}", "--system-prompt", SYSTEM, "--permission-mode", "dontAsk"]
    if model:
        cmd += ["--model", model]
    if resume:
        cmd += ["--resume", resume]
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=cwd, stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await asyncio.wait_for(proc.communicate(), RUN_TIMEOUT)
    return [json.loads(line) for line in out.decode().splitlines() if line.strip().startswith("{")]


def collect(events: list[dict], calls: list[dict], answers: list[str]) -> tuple[str | None, float]:
    pending: dict[str, dict] = {}
    session, cost, text = None, 0.0, []
    for e in events:
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "tool_use":
                    call = {"name": c["name"].removeprefix(PREFIX), "input": c["input"], "output": None}
                    pending[c["id"]] = call
                    calls.append(call)
                    text = []
                elif c["type"] == "text":
                    text.append(c["text"])
        elif e.get("type") == "user":
            for c in e["message"]["content"]:
                if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in pending:
                    content = c.get("content")
                    raw = content if isinstance(content, str) else "".join(x.get("text", "") for x in content or [])
                    try:
                        pending[c["tool_use_id"]]["output"] = json.loads(raw)
                    except ValueError:
                        pending[c["tool_use_id"]]["output"] = raw
        elif e.get("type") == "result":
            session, cost = e.get("session_id"), e.get("total_cost_usd") or 0.0
            if e.get("result"):
                text = [e["result"]]
    answers.append("\n".join(text))
    return session, cost


async def run_one(scenario: dict, mcp_config: str, model: str | None) -> dict:
    calls, answers, cost = [], [], 0.0
    with tempfile.TemporaryDirectory() as cwd:   # no project CLAUDE.md / settings leak in
        session, c = collect(await claude(scenario["question"], mcp_config, cwd, model, None), calls, answers)
        cost += c
        for reply in scenario.get("user_replies") or []:
            if not session:
                break
            session, c = collect(await claude(reply, mcp_config, cwd, model, session), calls, answers)
            cost += c
    return {"calls": calls, "answers": answers, "cost_usd": cost}


# ── grading ───────────────────────────────────────────────────────────────
def executed(calls: list[dict]) -> tuple[list[str], list[str]]:
    """(method names and recipe:<name> executed, result statuses) from the tool calls."""
    names, statuses = [], []

    def result(r: Any, method: str | None) -> None:
        if isinstance(r, dict) and r.get("status") in ("success", "needs_input", "refused", "failed"):
            statuses.append(r["status"])
            if method:
                names.append(method)

    for c in calls:
        i, o = c["input"], c["output"]
        if c["name"] == "run_method":
            result(o, i.get("name"))
        elif c["name"] == "run_step":
            result(o, i.get("method"))
        elif c["name"] == "start_run" and isinstance(o, dict) and "steps" in o:
            names.append(f"recipe:{i.get('recipe')}")
            for s in o["steps"]:
                result(s.get("result"), s.get("method"))
    return names, statuses


def numbers_in(value: Any) -> list[float]:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return [float(n.replace(",", "")) for n in NUMBER.findall(text)]


def grounded(x: float, pool: list[float]) -> bool:
    decimals = len(str(abs(x)).split(".")[1]) if "." in str(x) else 0
    tol = 0.5 * 10 ** -decimals + 1e-9
    # the same number shown as a percentage or in display units (thousand, 만, million, 억)
    scales = (1, 100, 1e-3, 1e-4, 1e-6, 1e-8)
    return any(abs(abs(p) * k - abs(x)) <= tol for p in pool for k in scales)


def derivable(x: float, pool: list[float]) -> bool:
    """x is a tool number, or a sum / difference / ratio(%) of two of them, at x's precision."""
    if grounded(x, pool):
        return True
    decimals = len(str(abs(x)).split(".")[1]) if "." in str(x) else 0
    tol = 0.5 * 10 ** -decimals + 1e-9
    values = sorted({abs(p) for p in pool if p})[:400]
    for i, a in enumerate(values):
        for b in values[i:]:
            for v in (a + b, abs(a - b), a / b * 100, b / a * 100, a / b, b / a):
                if any(abs(v * k - abs(x)) <= tol for k in (1, 1e-4, 1e-8)):
                    return True
    return False


def grade(s: dict, run: dict) -> dict:
    names, statuses = executed(run["calls"])
    answers = run["answers"]
    final = "\n".join(answers)
    checks: dict[str, bool] = {"answered": bool(final.strip())}
    if s.get("must_call"):
        checks["must_call"] = all(n in names for n in s["must_call"])
    if s.get("must_call_any"):
        checks["must_call_any"] = any(n in names for n in s["must_call_any"])
    if s.get("expect_status"):
        checks["expect_status"] = all(x in statuses for x in s["expect_status"])
    if s.get("must_ask_user"):
        checks["asked_user"] = bool(answers) and "?" in answers[0]
    if s.get("expect_numbers"):
        tol = s.get("tolerance", 0.01)
        found = numbers_in(answers[-1] if answers else "")
        checks["expect_numbers"] = all(any(abs(abs(f) - n) <= tol for f in found) for n in s["expect_numbers"])
    if s.get("must_mention"):
        checks["must_mention"] = all(m in final for m in s["must_mention"])
    if s.get("must_mention_any"):
        checks["must_mention_any"] = any(m in final for m in s["must_mention_any"])
    if s.get("must_not_mention"):
        checks["must_not_mention"] = not any(m in final for m in s["must_not_mention"])
    if s.get("must_call_tools"):
        checks["must_call_tools"] = set(s["must_call_tools"]) <= {call["name"] for call in run["calls"]}
    if s.get("must_not_call"):
        checks["must_not_call"] = not set(s["must_not_call"]) & set(names)
    if s.get("require_single_run"):
        ids = {call["input"]["run_id"] for call in run["calls"]
               if call["name"] in {"run_step", "use_recipe", "complete_run"} and call["input"].get("run_id")}
        ids.update(call["output"]["run_id"] for call in run["calls"]
                   if call["name"] in {"start_run", "start_analysis"} and isinstance(call["output"], dict)
                   and call["output"].get("run_id"))
        checks["single_run"] = len(ids) == 1
    completed = [call["output"] for call in run["calls"] if call["name"] == "complete_run"
                 and isinstance(call["output"], dict) and call["output"].get("status") == "completed"]
    if s.get("require_run_coverage"):
        checks["run_coverage"] = bool(completed) and all(
            item.get("goals") and {goal["id"] for goal in item["goals"]} ==
            {outcome["goal_id"] for outcome in (item.get("conclusion") or {}).get("goal_outcomes", [])}
            for item in completed)
    if s.get("expect_goal_statuses"):
        actual = {outcome["status"] for item in completed
                  for outcome in (item.get("conclusion") or {}).get("goal_outcomes", [])}
        checks["goal_statuses"] = set(s["expect_goal_statuses"]) <= actual
    if s.get("must_use_recipe"):
        checks["recipe_reused"] = bool(completed) and all(
            item.get("recipe") == s["must_use_recipe"] and
            (item.get("recipe_invocation") or {}).get("completed") and
            any(review.get("decision") == "selected" and review.get("recipe") == s["must_use_recipe"]
                for review in item.get("recipe_review", [])) for item in completed)
    pool = [n for c in run["calls"] for n in numbers_in(c["output"])] + numbers_in(s["question"]) \
        + numbers_in(" ".join(s.get("user_replies") or []))
    decimals = [x for x in numbers_in(final) if x != int(x)]
    ungrounded = [x for x in decimals if not grounded(x, pool)]
    checks["numbers_grounded"] = not ungrounded
    underivable = [x for x in ungrounded if not derivable(x, pool)]
    answer_checks = {k: v for k, v in checks.items() if k != "numbers_grounded"}
    return {"executed": names, "statuses": statuses, "checks": checks, "ungrounded_numbers": ungrounded,
            "underivable_numbers": underivable, "numbers_derivable": not underivable,
            "answer_passed": all(answer_checks.values()) and not underivable,
            "passed": all(checks.values())}


# ── main ──────────────────────────────────────────────────────────────────
async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", type=Path)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--model", default=None, help="CLI model alias/id; default = the CLI's default model")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--env", action="append", default=[], help="KEY=VALUE for the MCP server")
    ap.add_argument("--label", default="")
    args = ap.parse_args()

    scenarios = json.loads(args.scenarios.read_text())["scenarios"]
    if args.only:
        scenarios = [s for s in scenarios if s["id"] in args.only]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + (f"-{args.label}" if args.label else "")
    out_dir = args.scenarios.resolve().parent / "results" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    mcp_config = out_dir / "mcp.json"
    env = {"DL_API_URL": os.environ.get("DL_API_URL", "http://127.0.0.1:8000")}
    if os.environ.get("DL_TOKEN"):
        env["DL_TOKEN"] = os.environ["DL_TOKEN"]
    env.update(kv.split("=", 1) for kv in args.env)
    mcp_config.write_text(json.dumps({"mcpServers": {SERVER: {
        "command": str(ROOT / ".venv" / "bin" / "decision-layer-mcp"), "env": env}}}))

    semaphore = asyncio.Semaphore(args.parallel)
    report: list[dict] = []

    async def job(s: dict, rep: int) -> None:
        async with semaphore:
            try:
                run = await run_one(s, str(mcp_config), args.model)
                graded = grade(s, run)
            except Exception as e:  # noqa: BLE001 — keep the rest of the batch going
                run, graded = {"error": repr(e), "calls": [], "answers": []}, {"checks": {"ran": False}, "passed": False}
        (out_dir / f"{s['id']}-{rep}.json").write_text(
            json.dumps({"scenario": s, "run": run, "grade": graded}, ensure_ascii=False, indent=2, default=str))
        report.append({"id": s["id"], "repeat": rep, "cost_usd": run.get("cost_usd", 0.0), **graded})
        failed = [k for k, v in graded["checks"].items() if not v]
        print(f"{s['id']}#{rep}: {'PASS' if graded['passed'] else 'FAIL'} {failed} "
              f"executed={graded.get('executed')} ungrounded={graded.get('ungrounded_numbers')}", flush=True)

    await asyncio.gather(*[job(s, r) for s in scenarios for r in range(args.repeats)])
    for s in scenarios:
        mine = [r for r in report if r["id"] == s["id"]]
        paths = [tuple(r.get("executed") or []) for r in mine]
        for r in mine:
            r["path_consistency"] = max(paths.count(p) for p in paths) / len(paths) if paths else 0
    keys = sorted({k for r in report for k in r["checks"]})
    summary = {"runs": len(report), "passed": sum(r["passed"] for r in report),
               "pass_rate": round(sum(r["passed"] for r in report) / len(report), 3) if report else None,
               "answer_pass_rate": round(sum(r.get("answer_passed", False) for r in report) / len(report), 3) if report else None,
               "numbers_derivable": round(sum(r.get("numbers_derivable", False) for r in report) / len(report), 3) if report else None,
               "path_consistency": round(sum(r["path_consistency"] for r in report) / len(report), 3) if report else None,
               "cost_usd": round(sum(r["cost_usd"] for r in report), 2),
               **{k: round(sum(r["checks"][k] for r in report if k in r["checks"])
                           / max(1, sum(k in r["checks"] for r in report)), 3) for k in keys}}
    (out_dir / "summary.json").write_text(json.dumps({"summary": summary, "runs": report}, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"results: {out_dir}")
    sys.exit(0 if summary["passed"] == summary["runs"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
