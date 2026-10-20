# Connect AI tools

Connect MCP so AI can discover and execute registered Methods and Recipes. Start the [Decision Layer server](quickstart.md) first.

The adapter runs on your computer and calls the Decision Layer API. Use a client that supports local stdio MCP servers.

Keep the server terminal running. Use another terminal with the same virtual environment activated for the commands below.

## Install the adapter

In the virtual environment where Decision Layer is installed:

```bash
pip install --pre 'decision-layer[mcp]'
which decision-layer-mcp
```

Replace `/absolute/path/decision-layer-mcp` below with the reported executable path. Match the API and Web URLs to your server's ports.

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui -- /absolute/path/decision-layer-mcp
codex mcp list
```

[Codex MCP](https://developers.openai.com/codex/mcp)

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui --transport stdio decision-layer -- /absolute/path/decision-layer-mcp
claude mcp list
```

[Claude Code MCP](https://code.claude.com/docs/en/mcp)

## Claude Desktop

Open **Settings → Developer → Edit Config** in the desktop app. On macOS, the file is:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Add `decision-layer` alongside existing `mcpServers` entries.

```json
{
  "mcpServers": {
    "decision-layer": {
      "command": "/absolute/path/decision-layer-mcp",
      "env": {
        "DL_API_URL": "http://127.0.0.1:8000",
        "DL_WEB_URL": "http://127.0.0.1:8000/ui"
      }
    }
  }
}
```

Save, fully quit Claude Desktop, and reopen it. See the [official local MCP guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers) for details.

## Ask and inspect the result

First ask which metrics and analysis methods are available to check the connection. With the sample running, continue with:

> Which department leads revenue in February 2026, and what is its revenue by region? Show the metrics and evidence used.

AI reads registered methods and the semantic catalog, selects inputs and asks about ambiguous meanings or dates.

Open the returned Run link to inspect results and queries. Save a recurring analysis as a [Recipe](recipes.md).

## Connection settings

| Variable | Purpose |
|---|---|
| `DL_API_URL` | Decision Layer API URL |
| `DL_WEB_URL` | Admin console URL for result links |
| `DL_TOKEN` | Bearer token required for an existing Cube user |
| `DL_LOCALE` | Method message language; use `ko` for Korean |

The sample contains revenue, departments and regions for January–March 2026. Grocery leads February revenue at 6,720.

The sample uses a local test identity. Keep real tokens in private client settings, outside Git.

## Troubleshoot

- **Executable missing**: check its path and virtual environment with `which decision-layer-mcp`.
- **Connection refused**: check that the server is running and `DL_API_URL` uses its port.
- **Access error or missing metrics**: check token and source permissions in [Connect Cube](cube.md).
- **No tools**: restart the client or MCP session.

Running the adapter directly in a terminal may wait for input. The MCP client supplies protocol requests.
