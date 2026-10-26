# Connect AI tools

Keep the [Decision Layer server](quickstart.md) running. Open another terminal and activate the virtual environment used for installation.
Connect one of the clients below.

## Codex

```bash
codex mcp add decision-layer --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui -- "$(command -v decision-layer-mcp)"
codex mcp list
```

## Claude Code

```bash
claude mcp add --scope user --env DL_API_URL=http://127.0.0.1:8000 --env DL_WEB_URL=http://127.0.0.1:8000/ui --transport stdio decision-layer -- "$(command -v decision-layer-mcp)"
claude mcp list
```

## Claude Desktop

Open **Settings → Developer → Edit Config**. First, find the executable:

```bash
which decision-layer-mcp
```

Replace `command` with that path and add the entry to your existing `mcpServers`:

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

Save, fully quit the app and reopen it.

## Ask a question

Check the connection:

> Show the available metrics and analysis methods.

Then try the sample:

> For February 2001 in the sample, find the department with the highest retailer receipts and show its receipts by store.

AI selects a Method and data; Decision Layer queries and calculates. Open the Run link in the answer to inspect results and queries.
See [the Python Method example](../tutorials/write-your-method.md) for tool requests and responses.

## Connection settings

If you changed the server port, update `DL_API_URL` and `DL_WEB_URL`.

| Variable | Purpose |
|---|---|
| `DL_API_URL` | API URL |
| `DL_WEB_URL` | Admin UI URL for result links |
| `DL_TOKEN` | Cube user authentication token |
| `DL_LOCALE` | Message language; use `ko` for Korean |

## Troubleshoot

- **`ENOENT`**: activate the virtual environment and check `which decision-layer-mcp`. Remove an incorrect Claude Code registration with `claude mcp remove --scope user decision-layer`, then reconnect.
- **API connection failed**: check that the server is running and the port matches.
- **Access error**: check authentication in [Connect Cube](cube.md).
- **No tools**: restart the AI client.
