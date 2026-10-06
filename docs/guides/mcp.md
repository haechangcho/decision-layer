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

With the [Complete Journey sample](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) running, ask:

> Across all available data, which product department has the largest retailer receipts? Show the analysis steps and evidence.

The reference leader is GROCERY at 4,093,814.14 retailer receipts. Source day indices are mapped to example calendar dates, not actual purchase years. Ask the client to preserve your original question, explain each step's purpose and return the Run ID. Open `/runs` in Web to inspect the graph, results, settings, queries and sources.

A suitable Recipe should be used first. Otherwise, the client can discover semantic objects and registered Methods, then use `start_analysis`, `run_step` and `complete_run` to record exploration under one question. Tool selection and narrative are the client's responsibility, not verified evidence.

Every Method executes through `run_step` on an existing Run ID, with a required purpose. There is no standalone `run_method` MCP tool. Keep one Run for the full question, including follow-up drilldowns and peer comparisons. Even a one-step analysis starts a Run. The API rejects blank questions, missing purposes and conclusions without links to recorded steps. Pipelines also remain open until a conclusion is saved. If the client stops early, Web shows **Awaiting conclusion** and lets the owner review results and finish the analysis before registering the whole procedure as a Recipe. Restart MCP clients after updating so they discover the current tools.

Use **Register as Recipe** on a completed Run to save its procedure immediately, without a configuration dialog. Purposes, Method versions and analytical settings are retained; group targets default to runtime selection rather than previous winners. Run-specific dates and shared filters are not silently fixed into the Recipe. Use **Edit before saving** for custom fixed settings. There is no automatic background registration. Adding to an existing Recipe and a shared approval inbox are not implemented. A recorded Method version that is no longer installed requires review.

## Authentication

The local Cube and dbt samples enable a development service identity, so they need no `DL_TOKEN`. For an existing source, set `DL_TOKEN` to its bearer token in the adapter's private environment. Use the same source and identity in Web and MCP to access the same Runs. See [Cube connection](cube.md) or [dbt Semantic Layer](dbt.md). Never commit tokens or reuse sample secrets in a shared deployment.

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

## Preserve Selection Rules

Ordinary drilldown results include `step_id` and `selection_sources`. When following the highest-ranked group, pass the returned `path` source as the next step's `drill_path` rather than copying the observed name. For a leading member's peer comparison, use its `condition` source as `subject` and its `parents` source as `peers`. The engine records the rule and resolved values together; incomplete output cannot select a winner, and ties ask for input.

A Run may use literal targets. Direct registration defaults to new runtime-selection rules or required typed inputs, not remembered targets. Explicit Recipe fixed policies remain fixed. Recipe `inputs` appear in `list_recipes`; supply declared inputs to `start_run`. See [Recipe authoring](recipes.md).
