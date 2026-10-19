# Build a Method project

Keep Python Methods and Skills in **one project's `methods/` directory**.
Local Python, CLI inspection and API startup read the same definitions.

## 0. Install from a checkout

Use Python 3.11+ and a Decision Layer checkout containing the project CLI.
Create a separate practice environment and install the local code:

```sh
mkdir -p ~/Workspace/dl-method-lab
cd ~/Workspace/dl-method-lab
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '/path/to/decision-layer[stats]'
decision-layer --help
```

Replace `/path/to/decision-layer` with your checkout's absolute path. `[stats]`
installs pandas and the statistical dependencies used in the examples. Install
the checkout containing these CLI changes rather than an older release. Activate
this environment again in a new terminal.

## 1. Create a project and definitions

Use the environment with Decision Layer installed. Repository development also
supports the equivalent `python -m decision_layer` command.

```sh
decision-layer init my_team
cd my_team
decision-layer new python rank
decision-layer new skill metric_review
```

```text
my_team/
├── decision-layer.yaml           # name: my_team
└── my_team/                      # importable Python package
    └── methods/
        ├── rank/
        │   └── method.py         # ordinary function + one METHOD object
        └── metric_review/
            └── SKILL.md          # YAML metadata + analytical guidance
```

Generated `__init__.py` files are omitted here. Only `method.py` and uppercase
`SKILL.md` are definition entries; helper files are not collected as Methods.
Each definition directory contains one entry type.

## 2. Edit a function or Skill

`my_team/methods/rank/method.py` contains:

```python
from decision_layer.methods import Column, DataInput, python_method


def analyze(data, descending=True):
    """Rank observed groups by a selected metric."""
    return data.assign(
        rank=data["value"].rank(method="min", ascending=not descending)
    )


METHOD = python_method(
    analyze,
    name="my_team.rank",
    version="1.0.0",
    inputs={"data": DataInput(columns={
        "value": Column(source="measure"),
        "group": Column(source="dimension"),
    })},
)
```

Run the ordinary function directly with a DataFrame. `METHOD` is the entry read
by the loader. No per-file `METHODS` list or per-module environment setting is
needed. Matching Column names are passed to function arguments automatically.
Bind actual semantic objects and dates at execution time.

The generated function is called `analyze`. Run it directly from the project root
(the directory containing `decision-layer.yaml`):

```sh
python - <<'PY'
import pandas as pd
from my_team.methods.rank.method import analyze

data = pd.DataFrame({"group": ["A", "B", "C"], "value": [30, 20, 20]})
print(analyze(data).to_string(index=False))
PY
```

The generated calculation produces ranks `1.0, 2.0, 2.0`. Edit the function and
rerun this command to compare the result.

For a Skill, edit the name, version, description and body of `SKILL.md`. The
scaffold creates a query-executing Skill using recorded Cube queries. Prose does
not replace analytical calculations or validation. Compose existing Methods in a
Recipe when execution order must be fixed.

## 3. Inspect registration

```sh
decision-layer check
decision-layer list
decision-layer list --json
```

`list` shows **name, version, kind and source path**, including built-in Methods.
`check` validates registration and Skill references. It does not query Cube or
validate numerical correctness. Duplicate names, malformed Python exports and
invalid Skills fail with source locations.

Load the same project in a notebook:

```python
session.load_project("/path/to/my_team")
session.list_methods()
session.find_methods(names=["my_team.rank"])
```

Loading adds definitions to the local session; it does not upload code. Restart
the kernel or check in a fresh process after editing imported modules.

## 4. Serve and use through AI

```sh
decision-layer serve --reload
```

The loader finds `decision-layer.yaml` in the current directory or its parents.
Use `--project /path/to/my_team` from elsewhere. Startup registers project
definitions in the existing Registry, making them available through Web, REST
and MCP. Development `--reload` restarts the API after Python, Skill or config edits.
Without a database override, CLI serve stores execution records in the project's
`.decision-layer/decision_layer.db`. An explicit `DL_DATABASE_URL` takes precedence.

For deployment, ship the reviewed project and its Python dependencies. Set
`DL_PROJECT_DIR=/opt/my_team` to **one project directory** and restart the API.
Copy or read-only mount that directory into a container. The CLI starts the API;
Web and MCP clients keep their existing connection configuration.

AI reads the list with `list_methods` and inputs with `describe_method`.
`find_methods` returns requirement-compatible candidates without deciding analytical
meaning. Execution uses the existing Run engine and records inputs, versions,
queries and results. Code stays in project files; startup rebuilds the registry.

Legacy `DL_METHOD_MODULES` / `METHODS` exports, `DL_SKILLS_DIR` and managed Web
releases remain supported. Remove an asset's old registration when moving it to
a project: duplicate names fail rather than silently overwrite.

The [complete example](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project)
contains ranking, OLS and a Skill. From the repository root:

```sh
python -m decision_layer check --project examples/methods/project
python -m decision_layer list --project examples/methods/project
```


## Open the installed admin UI

The Python distribution includes the admin console. Run `decision-layer serve
--reload` from the project and open the printed `/ui/` URL. No Node.js or product
checkout is required. The console loads the same project's Methods and canonical
API. Edit project code in files; use the console to choose inputs and inspect runs.
Live testing still requires a configured Cube source and credentials. Web editing
remains opt-in and does not overwrite project files.

Run storage defaults to `.decision-layer/decision_layer.db`, Recipes to `recipes/`,
and managed Method assets to `.decision-layer/method-assets`. Explicit environment
settings override these defaults. `serve --api-only` preserves API-only development.
Source contributors run `npm ci && npm run build:console` in `web/` before building
the wheel. Release automation performs this step.
