# Connect Cube

Connect Cube to analyze your organization's metrics and data.

## Start a project

Stop the demo with `Ctrl+C` if it is running, then:

```bash
decision-layer init my_team
cd my_team
decision-layer serve
```

## Connect

Open **Sources** in the admin UI.

1. Enter the Cube API URL and credentials.
2. Test the connection and save it.
3. Check the metrics and dimensions under **Metrics**.

| Cube location | Example API URL |
|---|---|
| Your computer | `http://127.0.0.1:4000/cubejs-api/v1` |
| Remote server | `https://your-cube.example/cubejs-api/v1` |
| Decision Layer runs in Docker | `http://host.docker.internal:4000/cubejs-api/v1` |

The URL must be reachable from the Decision Layer server.
Use a Cube user token for an existing deployment or a development API secret for local testing.
See [.env.example](https://github.com/haechangcho/decision-layer/blob/main/.env.example) for server authentication settings.

## Troubleshoot

- **Unreachable**: check `/cubejs-api/v1`, the port and network.
- **401 or 403**: check token expiry and permissions.
- **Missing metric or variable**: check Cube model definitions and access.

Continue by [creating a Recipe](recipes.md) or [connecting an AI client](mcp.md).
