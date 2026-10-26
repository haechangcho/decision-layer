# Connect AI tools

Connect MCP so AI can discover and execute registered Methods and Recipes. Start the [Decision Layer server](quickstart.md) first.

The adapter runs on your computer and calls the Decision Layer API. Use a client that supports local stdio MCP servers.

Keep the server terminal running. Use another terminal with the same virtual environment activated for the commands below.

## Prepare the connection

The MCP adapter is installed with Decision Layer. Activate the virtual environment used for installation.

The connection commands below use the installed executable's path automatically. Match the API and Web URLs to your server's ports.

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui -- "$(command -v decision-layer-mcp)"
codex mcp list
```

[Codex MCP](https://developers.openai.com/codex/mcp)

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui --transport stdio decision-layer -- "$(command -v decision-layer-mcp)"
claude mcp list
```

[Claude Code MCP](https://code.claude.com/docs/en/mcp)

## Claude Desktop

Open **Settings → Developer → Edit Config** in the desktop app. On macOS, the file is:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

Find the executable path first:

```bash
which decision-layer-mcp
```

Replace `command` in the JSON below with that path, then add `decision-layer` alongside existing `mcpServers` entries.

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

> Using the example calendar, which department leads retailer receipts in February 2001, and what are its receipts by store? Show the metrics and query evidence.

AI follows this flow:

1. Read `list_methods` and `describe_method` to choose a procedure and understand its inputs.
2. Call `get_semantic_catalog()` to read all available definitions and select metrics and dimensions.
3. Execute with `start_analysis` and `run_step`, or reuse a suitable Recipe, then explain the recorded results.

The catalog contains definitions from Cube `/meta`, not data rows. No search term or prior knowledge of internal Cube names is needed. AI asks about ambiguous meanings or dates; actual rows are queried when the analysis executes.

See the [Python function example](../tutorials/write-your-method.md) for calls and responses.

Open the returned Run link to inspect results and queries. Save a recurring analysis as a [Recipe](recipes.md).

## Connection settings

| Variable | Purpose |
|---|---|
| `DL_API_URL` | Decision Layer API URL |
| `DL_WEB_URL` | Admin console URL for result links |
| `DL_TOKEN` | Bearer token required for an existing Cube user |
| `DL_LOCALE` | Method message language; use `ko` for Korean |

New demos use the full Complete Journey purchase data. In February 2001 on the example calendar, GROCERY leads with retailer receipts of 178,255.38. Receipts are not profit, and the example dates do not represent actual purchase years.

Demos created with earlier versions keep their original synthetic data. Ask your AI client to check the available metrics and periods first.

The sample uses a local test identity. Keep real tokens in private client settings, outside Git.

## Troubleshoot

- **`ENOENT` or executable missing**: activate the environment where you installed the adapter and check `which decision-layer-mcp`. To replace an incorrect Claude Code registration, run `claude mcp remove --scope user decision-layer`, then repeat the connection command above.
- **Connection refused**: check that the server is running and `DL_API_URL` uses its port.
- **Access error or missing metrics**: check token and source permissions in [Connect Cube](cube.md).
- **No tools**: restart the client or MCP session.

Running the adapter directly in a terminal may wait for input. The MCP client supplies protocol requests.
