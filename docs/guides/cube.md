# Connect an existing Cube

Decision Layer does not need to own Cube's database or run Cube in the same stack.

## Start

From the repository root:

```bash
docker compose up -d --build --wait
```

Open **http://localhost:3000/sources**. Enter the full Cube REST API URL, select authentication, then test and save. Continue to Catalog, then create a Recipe or connect [MCP](mcp.md).

| Cube location | API URL example |
| --- | --- |
| On your computer, accessed by the Docker API | `http://host.docker.internal:4000/cubejs-api/v1` |
| Remote deployment | `https://your-cube.example/cubejs-api/v1` |
| Same Docker network | `http://cube:4000/cubejs-api/v1` |
| Both Cube and API run natively | `http://localhost:4000/cubejs-api/v1` |

Inside a container, `localhost` means that container. Root Compose supplies the host gateway mapping for `host.docker.internal`.

## Authentication

Use a token issued by your Cube deployment for token authentication. A URL alone works only when the source permits the selected access mode. Decision Layer does not mint enterprise identity tokens or bypass Cube authorization.

Development API-secret authentication is for local development, not production identity. The [sample](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/README.md) configures local credentials for you. Sharing a service identity requires explicit server configuration and changes the access boundary.

Saved connection secrets are encrypted. Environment overrides take precedence and appear locked in Sources. Keep the server encryption key stable when persisting configuration. See [.env.example](https://github.com/haechangcho/decision-layer/blob/main/.env.example) and [Architecture](../ARCHITECTURE.md). Variables in a Compose `.env` file reach containers only if `compose.yaml` forwards them.

## Ports and storage

```bash
WEB_PORT=3010 API_PORT=8010 docker compose up -d --build --wait
docker compose ps
docker compose logs --tail=100 api web
docker compose down
```

Use the changed API port in MCP. `down` preserves named Recipe and Run volumes; `down -v` deletes them. Recipes are YAML files; Runs are separate database records.

For a Git-managed Recipe folder, create `recipes/` and replace `recipes:/recipes` in `compose.yaml` with `./recipes:/recipes`. Web writes files but does not make Git commits or PRs.

## Troubleshoot

| Failure | Next action |
| --- | --- |
| Unreachable | Check API URL, container DNS, firewall and TLS from the API network. |
| 401/403 | Renew the token or request source access. |
| No visible cubes | Check deployed models and the identity's semantic permissions. |
| Missing date or supporting measure | Inspect Catalog readiness; fix the definition in Cube, not the Recipe. |

Application login and author-role enforcement are not implemented. Keep Web and API local or on a trusted private network. Cube permissions do not secure Recipe-write endpoints.
