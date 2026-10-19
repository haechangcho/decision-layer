# Save the procedure. Recompute the answer.

A small, synthetic shop makes the reuse behavior visible: Home leads revenue in
January, Grocery leads in February, and they tie in March. One saved procedure
must follow the new leader and ask for input when there is no unique leader.


## Install into Claude Code or Codex

From the cloned repository, with Node.js, Claude Code or Codex and running Docker:

```bash
node scripts/install.mjs setup --client claude
# Or choose Codex:
node scripts/install.mjs setup --client codex
```

Setup copies the runtime to `~/.local/share/decision-layer/runtime`, starts and
checks the sample, and registers `decision-layer-demo`. Restart the selected client and
ask the February question below. No local Python or manual MCP JSON is needed.
The bridge can restart stopped API dependencies while Docker is running.
Setup never overwrites a different server using the same name. Existing sample
Runs stay in Docker volumes. The Web viewer is optional.

`node scripts/install.mjs doctor` checks the services and registration;
`node scripts/install.mjs stop` stops services without deleting data.
For Codex diagnostics use `node scripts/install.mjs doctor --client codex`.
Remove the connection with `claude mcp remove decision-layer-demo` or
`codex mcp remove decision-layer-demo` for the selected client.
The installer is currently supported on macOS/Linux shells and Windows WSL2;
native Windows installation has not been validated.

## Run

Requirements: Git and running Docker with Compose v2. No warehouse account,
Python installation or model API key is needed for this scripted walkthrough.
Initial builds download container images and packages; this is not an offline installer.

From the repository root:

```bash
bash scripts/demo.sh
```

Open **http://localhost:3100/runs**. The script prints three direct Run links.
API port is 8100. These ports and the `decision-layer-quickstart` Compose project
are separate from Complete Journey. For occupied ports:

```bash
DL_DEMO_WEB_PORT=3200 DL_DEMO_API_PORT=8200 bash scripts/demo.sh
```

The first build can take several minutes; do not interpret the small data size as
an installation-time guarantee. On failure, use the logs command printed by the script.

## What actually runs

1. The public REST API starts a January Run.
2. Registered `query.drilldown` queries a real Cube server for department revenue.
3. A second drilldown uses the first step's `ranked_groups` selection to query regions.
4. The script records an evidence-linked execution summary and registers the Run as a Recipe.
5. The same saved Recipe runs on February data, selecting Grocery instead of Home.
6. March's equal leaders require input before a regional query executes.

| Period | Leading department | Revenue | Leading region / revenue |
| --- | --- | ---: | --- |
| January 2026 | Home | 6,200 | North / 3,720 |
| February 2026 | Grocery | 6,720 | North / 4,032 |
| March 2026 | Home and Grocery tie | 3,720 each | Not selected automatically |

The oracle above follows directly from `seed.sql`: one row per day, department
and region; North receives 60% and South 40%. All 360 rows are invented for this
repository and distributed under its Apache-2.0 license. The source owns the
metric formula in `cube/model/sales.yml`. A Recipe only references it.

Inspect the Run's requested selection rule, resolved department, query evidence,
Method versions and warnings. Revenue has no provider-declared sample-count
binding, so minimum sample-size checks are not applied; that warning remains visible.
The sample describes rankings, not causal explanations of revenue changes.

## Ask your AI

The scripted demo does not use an LLM. To try natural-language planning, install
`.[mcp]` in a local Python 3.11+ environment as described in the
[MCP guide](../../docs/guides/mcp.md). Point the adapter at API port **8100** and
set `DL_WEB_URL=http://localhost:3100`. For a stdio client's configuration:

```json
{
  "mcpServers": {
    "decision-layer-demo": {
      "command": "/absolute/path/decision-layer/.venv/bin/decision-layer-mcp",
      "env": {
        "DL_API_URL": "http://localhost:8100",
        "DL_WEB_URL": "http://localhost:3100"
      }
    }
  }
}
```

Restart the client and ask:

> Use Decision Layer to reuse the saved department investigation for February 2026.
> Find the leading revenue department, then break its revenue down by region.
> Explain the evidence and limitations.

Then ask for March. Model credentials belong to your client. The client must use
the tools; chat-only claims are not captured or validated by Decision Layer.

## Replay, evidence and shutdown

```bash
bash scripts/demo.sh replay
# Export only the synthetic demo evidence:
docker compose -f examples/quickstart/compose.yaml cp api:/data/quickstart-evidence.json /tmp/quickstart-evidence.json
bash scripts/demo.sh stop
```

Each replay creates fresh Runs and a Recipe. Stop preserves this example's data.
To explicitly discard only this example's containers and volumes:

```bash
docker compose -f examples/quickstart/compose.yaml down -v
```

Local service credentials share one identity. This demonstrates procedure reuse,
not separate-user authorization. Ports bind to loopback; sample credentials and
Cube development mode are not a production deployment configuration.

For larger public retail data, use [Complete Journey](../complete-journey/README.md).
