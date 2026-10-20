# Connect Cube

Decision Layer reads metrics and dimensions and queries data through Cube's REST API. Cube owns metric definitions and joins.

## Enter the connection

[Install and start](quickstart.md) the server, then open **Sources** in the admin console.

1. Enter the Cube API URL and authentication method.
2. Test the connection and save it.
3. Check that the required metrics and dimensions appear in **Metrics**.

| Cube location | Example API URL |
|---|---|
| Same computer | `http://127.0.0.1:4000/cubejs-api/v1` |
| Remote server | `https://your-cube.example/cubejs-api/v1` |
| Decision Layer runs inside Docker | `http://host.docker.internal:4000/cubejs-api/v1` |

The address must be reachable from the Decision Layer server. Inside a container, `localhost` refers to that container.

## Authentication

For an existing deployment, use a user token issued by that Cube environment. API-secret authentication and sample credentials are for local testing.

Saved credentials are encrypted; environment settings take precedence. See [.env.example](https://github.com/haechangcho/decision-layer/blob/main/.env.example) for connection administration settings.

## Troubleshoot

| Symptom | Check |
|---|---|
| Unreachable | `/cubejs-api/v1` in the URL, port and network |
| 401 or 403 | Token expiry and access scope |
| No metrics | Deployed Cube models and the user's model access |
| Missing date or variable | Whether Cube defines the required object |

Continue with [Recipes](recipes.md) or [AI tools](mcp.md).
