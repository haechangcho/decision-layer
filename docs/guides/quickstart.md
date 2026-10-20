---
title: Install and start
description: Install from PyPI, then use the sample or connect your Cube server.
---

# Install and start

Install with Python 3.11 or later. The package includes the admin Web UI.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade --pre 'decision-layer[stats,mcp]'
```

`stats` includes data and statistical libraries; `mcp` includes the AI connection adapter.

Use `--pre` while Decision Layer is a prerelease. Then choose a starting point.

## Try the sample

Start Docker with Compose v2, then run:

```bash
decision-layer demo
```

The command prepares PostgreSQL and Cube in Docker, then runs the admin UI and API
from your installed Python package. No company data or AI connection is needed.
The first start downloads Docker images and can take several minutes.

Open [the admin UI](http://127.0.0.1:8000/ui/recipes). The prepared analysis shows:

1. January: select Home as the highest-revenue department and inspect its regions.
2. Save the procedure as a Recipe.
3. February: reuse the Recipe and select the new leader, Grocery.
4. March: ask for a selection when two departments tie for first place.

Inspect inputs, queries and results in [Runs](http://127.0.0.1:8000/ui/runs).
This runs registered procedures on synthetic data; it does not generate answers with an AI model.

### Stop and keep your data

Press `Ctrl+C` in the running terminal to stop the server and sample containers.
Data, Recipes and Runs are kept. Run `decision-layer demo` again to restart.

The sample project lives in `~/.decision-layer/demo/`.
Editable Method files live in its `sample_shop/methods/` directory; startup prints this path.
An older empty demo gains these files on its next start. Custom definitions and execution history are preserved. Source data lives in the
sample's Docker PostgreSQL volume; Run history lives in `.decision-layer/runs.db`
inside the sample project.

If startup was interrupted and containers remain running, stop them with:

```bash
decision-layer demo stop
```

Choose another directory or available ports if needed. The selected ports are
reused on later starts. Pass the same `--directory` when stopping a custom sample.

```bash
decision-layer demo --directory ./sample_shop --port 8010 --cube-port 4110
```

## Connect your Cube server

If you already have Cube, create your team's project:

```bash
decision-layer init my_team
cd my_team
decision-layer serve
```

Follow [Connect Cube](./cube.md) to configure the server endpoint and credentials.
Use [Method projects](./method-projects.md) to add your team's Methods and Skills.

New demo and team projects include editable Skill and Python Method files. See [project files and tests](./method-projects.md) to inspect, modify and test them.

## Reuse with your AI

Follow [MCP setup](./mcp.md) to connect your AI client.
For the default demo, use API URL `http://127.0.0.1:8000` and Web URL
`http://127.0.0.1:8000/ui`.

> Reuse the saved department investigation for February 2026. Show the leading
> department, its regional revenue and the evidence.

## Develop Decision Layer

To change product code or the admin UI, follow [Local development](./development.md).
The original all-Docker sample is available in the
[repository examples](https://github.com/haechangcho/decision-layer/tree/main/examples/quickstart).
