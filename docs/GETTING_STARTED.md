# Connecting Decision Layer

Start the API and Web using the commands in the [README](../README.md#get-started). Python 3.11+ and Node.js 22 are required for that source-based setup. Docker Compose is only used by the optional [sample-data demo](../examples/ecommerce/README.md).

## Cube connection

1. Open http://localhost:5210/sources.
2. Enter your Cube REST API URL, for example `https://cube.example.com/cubejs-api/v1`.
3. Select access-token authentication and enter a token accepted by your Cube deployment.
4. Test and save the connection, then open the catalog.

The URL must be reachable from the API server. Within Docker, `localhost` means the container itself; use a reachable host or service name. No Cube instance is installed by Decision Layer.

Testing confirms catalog access. Query access and Method requirements are checked when an analysis executes. Cube must validate tokens and apply the intended access policies. Development-only anonymous access or API-secret signing requires `DL_ALLOW_SERVICE_CREDENTIALS=true` and explicit configuration.

Local installs without `DL_SOURCE_ADMIN_TOKEN` allow source editing. Set that administrator key before using a shared deployment. Caller tokens entered in Sources are kept in browser session storage, not saved as shared credentials in the database.

## Recipe files and Runs

Set `DL_RECIPES_DIR` to a writable directory for your Recipe YAML files and `DL_RECIPE_ADMIN_TOKEN` to the key used to authorize editing. The README uses `./recipes` and an example key for local development. Use a private key in a shared deployment.

Runs use SQLite at `data/decision_layer.db` by default. To use another database, set `DL_DATABASE_URL` to `sqlite:///path/to/file.db` or a PostgreSQL connection URL. `memory` storage is temporary. Preserve the database with a volume when running in a container.

## MCP

Installing `.[mcp]` adds the `decision-layer-mcp` stdio command. For clients with a `mcpServers` configuration:

```json
{
  "mcpServers": {
    "decision-layer": {
      "command": "/absolute/path/to/decision-layer/.venv/bin/decision-layer-mcp",
      "env": {
        "DL_API_URL": "http://localhost:8000",
        "DL_TOKEN": "<your Cube access token>"
      }
    }
  }
}
```

Replace the path and token, or use the client's secret configuration. Do not commit the populated configuration. Clients with another configuration format should use equivalent command and environment settings. `DL_LOCALE=ko` selects Korean tool messages.

The MCP adapter calls the REST API; keep the API running. Web and MCP must use the same API and an identity allowed to access the Run to retrieve the same records. Recipe investigations append steps to one Run; independent Method calls create separate Runs.

## Configuration

| Variable | Purpose |
| --- | --- |
| `CUBE_API_URL` | Provision a Cube endpoint; the Sources URL then becomes read-only |
| `DL_DATABASE_URL` | Run and source-configuration storage |
| `DL_RECIPES_DIR` | Recipe YAML directory |
| `DL_SOURCE_ADMIN_TOKEN` | Source-editing permission in shared deployments |
| `DL_RECIPE_ADMIN_TOKEN` | Recipe-editing permission |
| `DL_SOURCE_CONFIG_KEY` | Encryption key required to persist a source API secret |

Environment values override saved settings. See [`.env.example`](../.env.example) for other options. Supplying caller access tokens does not require storing a Cube signing secret.

Long-running requests can return `202` with a polling URL. Work runs inside the API process and does not resume after a restart. See the [architecture decisions](DECISIONS.md) for current operational limits.
