# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [Contributing](CONTRIBUTING.md)

**Make your team's analytical knowledge executable.**

Decision Layer is an open-source analysis layer for semantic models. Analysts turn recurring investigations into reusable **Recipes**. People and AI agents run those Recipes against the same governed metrics, with the results and evidence recorded.

![Decision Layer: metrics become reusable analysis recipes with recorded evidence](docs/assets/decision-layer-overview.png)

## Why Decision Layer?

A semantic layer defines what a metric means. Your team still needs to know how to analyze it.

For a question like "Why did revenue fall?", an experienced analyst might compare periods, examine product and regional contributions, then investigate the largest changes. Decision Layer captures that procedure so others can repeat it.

- **Reuse the procedure.** Combine registered analysis Methods into a versioned Recipe.
- **Keep existing definitions.** Use Cube's metrics, dimensions and access rules.
- **Run through Web or MCP.** Give people and AI clients the same execution engine.
- **Check the evidence.** Inspect inputs, results, queries, validation and warnings in each Run.

## How it works

| | Owns |
| --- | --- |
| **Cube** | Metric definitions, dimensions, joins and data access |
| **Method** | One analytical capability, such as a trend, drill-down or matched comparison |
| **Recipe** | The team's procedure, composed from Methods and semantic references |
| **Run** | What was executed, what it returned and the evidence behind it |

Web, REST and MCP share the same specifications and Python execution engine. Recipes are YAML files; Runs are stored in SQLite or PostgreSQL. AI clients select registered tools; Decision Layer does not host an LLM or execute AI-generated analysis code.

See [Architecture](docs/ARCHITECTURE.md) and [ADRs](docs/DECISIONS.md) for the contracts and current decisions.

## Get started

You need Docker with Compose and an existing Cube API.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
docker compose up -d --build --wait
```

Open **http://localhost:3000/sources**, enter your **Cube API URL and access token**, then test and save the connection. If Cube runs on your computer at port 4000, use `http://host.docker.internal:4000/cubejs-api/v1`. Explore your metrics and create a Recipe; the local Recipe editing key is `local-recipe-key`.

The first start builds the images; Python and Node.js are included. Recipes and execution records persist in Docker volumes. `docker compose down` stops the app without deleting them. The default setup is local-only; use private administrator keys and your own deployment configuration for a shared server.

Port in use? Run `WEB_PORT=3010 API_PORT=8010 docker compose up -d --build --wait` instead. No Cube yet? Try the [sample-data demo](examples/ecommerce/README.md). For source installation, see [Contributing](CONTRIBUTING.md).

## Use with AI agents

Connect Claude, Codex or another MCP client to `decision-layer-mcp`. The client can discover metrics, find Recipes, run analysis and retrieve the same execution records shown in the Web.

When a Recipe fits the question, the client is instructed to use it. Otherwise, it can invoke registered Methods. Tokens are passed to Cube so its access rules apply.

Install the MCP adapter with `pip install '.[mcp]'` from the repository root, then configure your client to run `decision-layer-mcp` with `DL_API_URL=http://localhost:8000` and `DL_TOKEN` set to your Cube access token. Use the same Cube identity in Web and MCP to access the same Runs.

## Project status

Early development. Cube integration, Method execution, Recipe graph editing and Run storage are available.

Next: simpler Recipe authoring, consistent defaults, and turning MCP execution records into Recipe graph drafts that users review and approve. The approval flow is not implemented yet.

[Example Recipes](examples/ecommerce/recipes/) · [Method implementations](src/decision_layer/methods/)

## Contributing

Contributions to Methods, Recipes, documentation and usability are welcome. Start with [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE).
