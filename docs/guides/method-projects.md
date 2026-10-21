# Register in a project

Save [the example function](../tutorials/write-your-method) in a project to use it through the admin UI and AI.
Python, CLI commands and the server read the same project files.

## Create a project

Run in the environment where you [installed Decision Layer](quickstart.md).

```bash
decision-layer init my_team
cd my_team
python -m pip install -e '.[test]'
```

Two Skills and two Python Methods are created as editable project files:

```text
my_team/
├── decision-layer.yaml
├── pyproject.toml
├── recipes/
└── methods/
    ├── metric_lookup/SKILL.md
    ├── drilldown/SKILL.md
    ├── ols/
    │   ├── method.py
    │   └── test_method.py
    └── matching/
        ├── method.py
        └── test_method.py
```

- `SKILL.md` contains instructions for AI queries and analysis.
- `method.py` contains the calculation and `METHOD = python_method(...)` registration.
- `test_method.py` checks known synthetic answers and invalid inputs.
- `pyproject.toml` declares project dependencies.

OLS uses statsmodels; matching uses scikit-learn. Results describe observed associations and group differences, without establishing causality.

## Check and serve

```bash
decision-layer check
decision-layer test
decision-layer list
decision-layer serve --reload
```

| Command | Purpose |
|---|---|
| `check` | Validate registration and references, without querying or calculating. |
| `test` | Run 13 OLS and matching tests, without Cube or a server. |
| `list` | Show names, versions and source paths. |
| `serve` | Start the admin UI and API with the same project. |

The default names are `analysis.metric_lookup`, `analysis.drilldown`, `stats.regression_adjustment` and `stats.binary_matching`.
New projects discover these local files. Remove a definition folder if it is not needed.

Open the printed admin URL, normally `http://127.0.0.1:8000/ui/`.
`--reload` restarts the server when files change. Run the tests and increment the Method version when changing a calculation.
From another directory, use `decision-layer serve --project /path/to/my_team`.

## Add a Method

```bash
decision-layer new python rank
decision-layer new skill metric_review
```

These create `methods/rank/method.py` and `methods/metric_review/SKILL.md`.
Use a [Recipe](recipes.md) to reuse a sequence of existing Methods.
Start without defaults with `decision-layer init my_team --empty`.

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

Package upgrades never overwrite project files or add defaults to ordinary existing projects.
An older empty managed demo gains starter files when `demo` runs again.
Use a new directory to repeat first-install QA. Older configurations retain their built-in catalog;
new configurations set `include_builtin_methods: false` to discover local project definitions instead.
