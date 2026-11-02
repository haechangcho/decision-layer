"""Connectivity smoke test only; this is not the paired Recipe benchmark.

Requires a running local Complete Journey demo and a signed-in Codex CLI.
The local demo secret is only used to create a short-lived Cube token; override
BENCH_CUBE_SECRET for a different local setup. Never use production credentials.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import jwt

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv/bin/python"
MCP = ROOT / ".venv/bin/decision-layer-mcp"


def main():
    env = os.environ.copy()
    env["BENCH_CUBE_URL"] = env.get("BENCH_CUBE_URL", "http://127.0.0.1:4100/cubejs-api/v1")
    env["BENCH_CUBE_TOKEN"] = jwt.encode(
        {"sub": "benchmark", "exp": int(time.time()) + 1800},
        env.get("BENCH_CUBE_SECRET", "local-quickstart-secret-change-me-0123456789"),
        algorithm="HS256",
    )
    env["DL_API_URL"] = env.get("DL_API_URL", "http://127.0.0.1:8000")
    cases = {
        "cube": (str(PYTHON), [str(HERE / "cube_baseline.py")], ["BENCH_CUBE_URL", "BENCH_CUBE_TOKEN"],
                 "Use the cube MCP get_catalog tool. Report whether the catalog has a receipts measure. Do not run shell commands."),
        "decision_layer": (str(MCP), [], ["DL_API_URL"],
                           "Use the decision_layer MCP get_semantic_catalog tool. Report whether the catalog has a receipts measure. Do not run shell commands."),
    }
    for name, (command, args, env_vars, prompt) in cases.items():
        config = {"command": command, "args": args, "env_vars": env_vars, "startup_timeout_sec": 60}
        # JSON's strings and arrays are valid TOML values inside this inline table.
        table = "{ " + ", ".join(f"{k} = {json.dumps(v)}" for k, v in config.items()) + " }"
        cmd = ["codex", "exec", "--ignore-user-config", "--skip-git-repo-check", "--ephemeral", "--json", "--approve-for-me",
               "-c", f"mcp_servers.{name}={table}", "-c", 'model_reasoning_effort="medium"', "-C", "/private/tmp", prompt]
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="dl-codex-smoke-") as work:
            result = subprocess.run(cmd, cwd=work, env=env, text=True, capture_output=True, timeout=300, stdin=subprocess.DEVNULL)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        calls = [e.get("item", {}) for e in events if e.get("item", {}).get("type") == "mcp_tool_call"]
        usage = next((e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None)
        messages = [e["item"].get("text", "") for e in events if e.get("item", {}).get("type") == "agent_message"]
        print(json.dumps({"condition": name, "exit_code": result.returncode, "elapsed_seconds": round(time.monotonic()-start, 2),
                          "mcp_calls": [{"server": x.get("server"), "tool": x.get("tool"), "status": x.get("status")} for x in calls],
                          "usage": usage, "answer": messages[-1] if messages else None,
                          "error": result.stderr[-1000:] if result.returncode else None}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
