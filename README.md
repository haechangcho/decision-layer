# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [Documentation](docs/README.md) · [Contributing](CONTRIBUTING.md)

**Make your team's analytical knowledge executable.**

Decision Layer connects governed metrics to reusable analysis procedures. Analysts combine registered **Methods** into **Recipes**; people and AI agents execute them through Web or MCP. Every **Run** records the question, results, queries and validation.

![From governed metrics to reusable analysis and recorded evidence](docs/assets/decision-layer-overview.png)

## Start

Try the retail example with eight related source tables. You need Docker with Compose; no existing database, Cube account or local token setup is required.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

Open **http://localhost:3000/catalog**. PostgreSQL, Cube, the API and Web start together, with the connection configured and Recipes empty. The first start builds images, downloads the official 128 MB archive and imports the source tables. Allow several minutes.

Already have Cube? Use the [existing Cube guide](docs/guides/cube.md) instead. See the [sample guide](examples/complete-journey/README.md) for ports, offline import, data provenance and stopping the stack.

## Connect an AI client

Keep the sample running. From the **repository root**, install the MCP adapter with Python 3.11+:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e '.[mcp]'
codex mcp add decision-layer --env DL_API_URL=http://localhost:8000 -- "$(pwd)/.venv/bin/decision-layer-mcp"
```

Using Claude or another client? Follow the [MCP guide](docs/guides/mcp.md). The adapter uses stdio and calls the same REST API as Web; Decision Layer does not host an LLM.

Ask your connected client:

> Across all available data, which product department has the largest retailer receipts? Break it down and show the evidence.

The independently checked largest department is **GROCERY, 4,093,814.14** in retailer receipts. Open **http://localhost:3000/runs** to inspect the question, metric graph and results. Review successful steps as a Recipe draft, then save and publish it for reuse. These reference checks verify execution, not an improvement in AI accuracy.

## How it works

| Object | Responsibility |
| --- | --- |
| **Semantic layer** | Metrics, dimensions, joins, grain and data access. Cube is the first supported provider. |
| **Method** | One typed analytical capability, with validation and structured results. |
| **Recipe** | A versioned procedure composed from Methods and semantic references. Stored as YAML. |
| **Run** | The executed question, steps, versions, queries, results and warnings. Stored in SQLite or PostgreSQL. |

Web, Python, REST and MCP share the same specifications and execution engine. AI clients use a suitable Recipe or explore with registered Methods; they cannot execute generated analysis code. Decision Layer is not a BI tool, semantic layer or scheduler.

## Develop and contribute

- [Develop locally](docs/guides/development.md): editable API and Web, with a shared sample source.
- [Run tests](docs/guides/testing.md): unit tests, browser tests and live MCP-to-Cube checks.
- [Add a Method](docs/guides/methods.md): contracts, registration, validation and contribution tests.
- [Contribute](CONTRIBUTING.md): changes, issues and pull requests.
- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/DECISIONS.md): ownership and execution contracts.

## Status

Early development. Cube integration, Recipe graph editing, previews, draft/publish versions and Run-to-Recipe review are available. Application login, author roles and a shared approval inbox are not implemented. The default setup is local-only; do not expose it as a shared public service. Sample credentials are for development only.

## License

[Apache License 2.0](LICENSE).
