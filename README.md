# Decision Layer

[Docs](https://decision-layer-docs.vercel.app/) · [한국어](README.ko.md)

**Make your team's analytical knowledge executable.**

Decision Layer connects semantic metrics to registered analytical **Methods** and reusable **Recipes**. Analyze through Web or AI clients, inspect the question, steps and evidence in a **Run**, then save the procedure for your team to reuse.

Web, Python, REST and MCP share one execution engine. AI clients select registered Methods and Recipes; they do not execute generated analysis code.

Unanswered questions can record missing semantic requirements alongside their evidence. Update the semantic model externally and ask again.

![A business question follows a reusable Recipe, executed through Web or AI with recorded evidence](docs/assets/decision-layer-overview.png)

## Start here

| Goal | Start with |
| --- | --- |
| Develop a Method | The Python-only workflow below |
| Develop Web/API | [Local development](docs/guides/development.md) |
| Try real data and the product | [Complete Journey sample](examples/complete-journey/README.md) |

## Develop your first Method

Python 3.11+ is enough. From a fresh clone:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
make setup
make example
```

Open `examples/methods/first_method/method.py`, change the implementation and run
`make example` again. Its test uses independent fixture data and checks the exact
semantic query. No source credentials, Web server, Node or Docker are required.
See [the Method guide](docs/guides/methods.md) for ordinary Python commands without Make.

```bash
.venv/bin/python -m pytest -q examples/methods/peer_comparison
make test
```

The peer example tests three queries and their combination. Optional notebooks import
these Python modules. [Contributing](CONTRIBUTING.md) explains the code map and checks.

## Try the product with sample data

With Docker and Compose installed:

```bash
cd examples/complete-journey
docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900
```

Open [localhost:3000](http://localhost:3000). First startup imports the dataset and
can take a few minutes. The sample starts without Recipes. See its guide for data
provenance and teardown. For existing sources, connect [Cube](docs/guides/cube.md) or
[the official dbt Semantic Layer API](docs/guides/dbt.md).

## Run Your First Analysis

1. [Connect Claude or Codex through MCP](https://decision-layer-docs.vercel.app/guides/mcp).
2. Ask: “Across all available data, which product department has the highest retailer receipts? Record the analysis steps and evidence.”
3. Open **Runs** in the Web app to review the analysis and save its steps and settings as a **Recipe**.

No Recipe is required for the first analysis. AI clients can use registered Methods directly.

To use your organization's data, connect [Cube](https://decision-layer-docs.vercel.app/guides/cube) or [dbt Semantic Layer](https://decision-layer-docs.vercel.app/guides/dbt). For reusable procedures, see [Recipes](https://decision-layer-docs.vercel.app/guides/recipes).

## Development

[Local setup](https://decision-layer-docs.vercel.app/guides/development) · [Tests](https://decision-layer-docs.vercel.app/guides/testing) · [Add a Method](https://decision-layer-docs.vercel.app/guides/methods) · [Architecture](https://decision-layer-docs.vercel.app/ARCHITECTURE) · [Contributing](CONTRIBUTING.md)

[Apache 2.0](LICENSE)
