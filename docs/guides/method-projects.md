# Use a Method project

Save [your function](methods.md) in a project to use it through the admin UI and AI.
Python, CLI commands and the server read the same project files.

## Create a project and definition

Run these commands in the environment where you [installed Decision Layer](quickstart.md).

```bash
decision-layer init my_team
cd my_team
decision-layer new python rank
```

```text
my_team/
├── decision-layer.yaml
└── my_team/methods/rank/
    └── method.py
```

Put your function and `METHOD = python_method(...)` in `method.py`. The CLI creates
a ranking function named `analyze` as a starting point. Import helper Python files
from the same directory as needed.

To register analytical guidance as a Skill:

```bash
decision-layer new skill metric_review
```

Edit the name, version, description and instructions in the generated
`my_team/methods/metric_review/SKILL.md`. Use a [Recipe](recipes.md) to reuse an
execution sequence of existing Methods. The [complete project](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)
contains ranking, OLS and a Skill.

## Check and serve

```bash
decision-layer check
decision-layer list
decision-layer serve --reload
```

- `check` validates registration and references, without querying or calculating.
- `list` shows names, versions, kinds and source paths.
- `serve` loads project Methods and starts the admin UI and API.

Open the printed admin URL, normally `http://127.0.0.1:8000/ui/`. `--reload` restarts
the server when files change. From another directory, use
`decision-layer serve --project /path/to/my_team`.

## Test in the admin UI

[Connect Cube](cube.md), then:

1. Select your registered Method under **Methods**.
2. Choose metrics, dimensions and dates under **Choose inputs and test**.
3. Inspect results and validation, then open **Runs** for queries and input evidence.

Notebook example data and local results are not uploaded automatically. The server
queries the configured Cube source.

## Use through AI

Follow [MCP setup](mcp.md) to connect to the same API. The default server uses:

```text
DL_API_URL=http://127.0.0.1:8000
DL_WEB_URL=http://127.0.0.1:8000/ui
```

AI inspects registered Methods and input contracts, then selects data from the
semantic catalog. The server records execution inputs, results and queries in a Run.

## Share with your team

Keep project files in your team's Git repository. Deploy reviewed files and Python
dependencies to the server, set `DL_PROJECT_DIR` and restart to load the project.

Runs are stored in `.decision-layer/decision_layer.db` and Recipes in `recipes/`.
Notebook, CLI and server share the loader but retain their own execution history.
Web-published versions are managed separately and do not overwrite project source.
