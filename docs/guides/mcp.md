# Connect an MCP client

The adapter runs locally over **stdio** and calls the Decision Layer REST API. Do not enter the API URL as a remote MCP endpoint. The API and Cube must be running; your AI client handles its own model credentials.

## Install

From the repository root, with Python 3.11+:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
```

Use the absolute path to `.venv/bin/decision-layer-mcp`. The examples use API port 8000; change it if your stack uses another port.

## Codex

From the repository root:

```bash
codex mcp add decision-layer --env DL_API_URL=http://localhost:8000 -- "$(pwd)/.venv/bin/decision-layer-mcp"
codex mcp list
```

Start a new session and check `/mcp`. See the [official Codex MCP guide](https://developers.openai.com/codex/mcp).

## Claude Code

From the repository root:

```bash
claude mcp add --scope user --env DL_API_URL=http://localhost:8000 --transport stdio decision-layer -- "$(pwd)/.venv/bin/decision-layer-mcp"
claude mcp list
```

Start a new session and check `/mcp`. User scope keeps machine-specific paths out of the repository. See the [official Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

## Claude Desktop

Merge this entry into your Desktop MCP configuration, replacing the command with your absolute path. Do not overwrite other servers.

```json
{
  "mcpServers": {
    "decision-layer": {
      "command": "/absolute/path/decision-layer/.venv/bin/decision-layer-mcp",
      "env": {"DL_API_URL": "http://localhost:8000"}
    }
  }
}
```

Restart the client. Other stdio clients use the same executable and environment, but may have different configuration formats.

## Ask and review

With the [Complete Journey sample](../../examples/complete-journey/README.md) running, ask:

> Across all available data, which product department has the largest retailer receipts? Show the analysis steps and evidence.

The reference leader is GROCERY at 4,093,814.14 retailer receipts. Source days are relative, not actual calendar dates. Ask the client to preserve your original question, explain each step's purpose and return the Run ID. Open `/runs` in Web to inspect the graph, results and folded execution evidence.

A suitable Recipe should be used first. Otherwise, the client can discover semantic objects and registered Methods, then use `start_analysis`, `run_step` and `complete_run` to record exploration under one question. Tool selection and narrative are the client's responsibility, not verified evidence.

Select successful steps in the Run and review them as a new Recipe candidate. This does not save or approve anything automatically. Check bindings, parameters and interpretation in the editor, save a draft, then publish deliberately. Adding to an existing Recipe and a shared approval inbox are not implemented.

## Authentication

The local sample explicitly enables a development service identity, so it needs no `DL_TOKEN`. For caller authentication, set `DL_TOKEN` to the Cube bearer token in the adapter's environment. Use the same Cube identity in Web and MCP to access the same Runs. Never commit tokens or reuse sample secrets in a shared deployment. See [Cube connection](cube.md).

`DL_LOCALE=ko` requests Korean Method messages; the default is English. Client-provided question, purpose and origin labels are context, not authenticated approval.

## Troubleshoot

| Symptom | Check |
| --- | --- |
| Executable not found | Use an absolute path; install the MCP extra in that virtual environment. |
| Connection refused | Check `DL_API_URL`, API `/health` and host port. |
| 401 or missing metrics | Verify the token, expiry and source access scope. |
| No tools | Restart the client/session and inspect its MCP logs. |
| Server waits silently in a terminal | Normal for stdio: the client supplies protocol messages. |
| Run missing in Web | Match API URL and caller identity; check the Run finished. |

[Live smoke tests](testing.md) verify protocol and execution, not natural-language planning by your AI client.
