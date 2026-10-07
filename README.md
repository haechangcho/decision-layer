# Decision Layer

[Docs](https://decision-layer-docs.vercel.app/) · [한국어](README.ko.md)

**Make your team's analytical knowledge executable.**

Decision Layer connects semantic metrics to registered analytical **Methods** and reusable **Recipes**. Analyze through Web or AI clients, inspect the question, steps and evidence in a **Run**, then save the procedure for your team to reuse.

Web, Python, REST and MCP share one execution engine. AI clients select registered Methods and Recipes; they do not execute generated analysis code.

![A business question follows a reusable Recipe, executed through Web or AI with recorded evidence](docs/assets/decision-layer-overview.png)

## Quickstart

With Docker and Compose installed, clone the project and choose **Cube or dbt**:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
```

**Cube**

```bash
docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900
```

**dbt MetricFlow**

```bash
docker compose -p decision-layer-dbt -f compose.yaml -f compose.dbt.yaml up -d --build --wait --wait-timeout 900
```

Each example keeps its database, connection settings, Runs and Recipes separately. They use the same ports, so run one at a time. Use the shutdown commands in the [sample guide](examples/complete-journey/README.md) before switching.

Run one option, then open [localhost:3000](http://localhost:3000). Both use the same dataset. The first start downloads and imports it and can take a few minutes.

The sample includes a connected semantic source and starts without Recipes. See the [sample guide](examples/complete-journey/README.md) for data details and teardown. This setup is for local development, not production.

The dbt example includes a local MetricFlow runtime for trying the product without a dbt account. Existing company environments connect directly through the official [dbt Semantic Layer API](https://decision-layer-docs.vercel.app/guides/dbt).

## Run Your First Analysis

1. [Connect Claude or Codex through MCP](https://decision-layer-docs.vercel.app/guides/mcp).
2. Ask: “Across all available data, which product department has the highest retailer receipts? Record the analysis steps and evidence.”
3. Open **Runs** in the Web app to review the analysis and save its steps and settings as a **Recipe**.

No Recipe is required for the first analysis. AI clients can use registered Methods directly.

To use your organization's data, connect [Cube](https://decision-layer-docs.vercel.app/guides/cube) or [dbt Semantic Layer](https://decision-layer-docs.vercel.app/guides/dbt). For reusable procedures, see [Recipes](https://decision-layer-docs.vercel.app/guides/recipes).

## Development

[Local setup](https://decision-layer-docs.vercel.app/guides/development) · [Tests](https://decision-layer-docs.vercel.app/guides/testing) · [Add a Method](https://decision-layer-docs.vercel.app/guides/methods) · [Architecture](https://decision-layer-docs.vercel.app/ARCHITECTURE) · [Contributing](CONTRIBUTING.md)

[Apache 2.0](LICENSE)
