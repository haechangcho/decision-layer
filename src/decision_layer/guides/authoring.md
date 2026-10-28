# Author a reusable analysis Method

Choose the smallest asset that solves the task:
- Skill: analytical instructions for choosing inputs, queries and interpretation. Opt into query_execution to make a recorded agent-driven Recipe stage. Prose alone never validates or grants access.
- Python: a reviewed ordinary function for a calculation existing tools cannot perform. Register with `python_method` and `DataInput`. No async, context or Decision Layer output class is required in the function.
- Recipe: connect query-executing Skills and registered Python calculations with explicit input propagation. Fixed sequences are replayable; agent choices may vary and are recorded.

Before writing code, use list_methods / describe_method. Read get_method_guide("cube-query") before selecting semantic inputs. Never embed official metric definitions in Python or infer a nonexistent Cube member.

## Ordinary Python

Create a project with `decision-layer init my_team`. It includes editable metric/drilldown Skills and OLS/matching Python files with tests. Install `python -m pip install -e '.[test]'` and run `decision-layer test` for known synthetic answers, without Cube. Add your own definitions with `decision-layer new python rank` or `decision-layer new skill metric_review` inside it. Python entries live in
`methods/rank/method.py` and export `METHOD`; Skill entries use `SKILL.md` in
their own definition folders. `decision-layer check` validates registration and
`decision-layer list` reports source paths. `serve` loads that same project into the
API. Local Python uses `session.load_project(path)` and `session.list_methods()`.

```python
from decision_layer.methods import DataInput, python_method


def rank_groups(data, descending=True):
    """Rank observed groups; preserve ties."""
    return data.assign(
        rank=data["value"].rank(ascending=not descending, method="dense")
    )


METHOD = python_method(
    rank_groups,
    name="my_team.rank",
    version="1.0.0",
    inputs={"data": DataInput(measures=["value"], dimensions=["group"])},
)
```
The server binds `value` and `group` to discovered Cube refs at execution. The input name `data` is the function argument. Scalar options infer types from annotations or defaults; otherwise use `parameters={"option": float}`. Wrap library functions with positional-only arguments or complex options. Multiple named data inputs are supported; give comparison inputs `period_parameter="baseline", period_role="comparison"`. Execution requires a Run period and a discovered time dimension. DataFrame is an in-memory calculation input, not a local file source.

Return a number, DataFrame, list of row dictionaries, or one dictionary. Use `output="estimate"` for NumPy scalars and `adapt=reviewed_function` for library result objects. Default interpretation remains association even when the library is called DoWhy. Declaring a package dependency does not install it or establish causal identification.

Checks are optional ordinary functions receiving named data inputs, returning None/True/False or raising ValueError/AssertionError. A failed check stops calculation. Source checks record minimum rows, required columns, finite measures and unique returned grain. Write and test design-specific checks; prose is never marked as executed validation. Inspect query evidence, warnings and failed checks before interpreting values.

## Common module and input contract
Ordinary functions may take column names explicitly: `ols(data, outcome, treatment,
confounders)`. Add `column_args=["outcome", "treatment", "confounders"]` to that
table's DataInput. Each name must be a declared measure/dimension/column role and an
actual function argument. The runtime supplies a string for scalar roles and a list
of strings for multiple roles, using the exact returned aliases. Optional missing
roles receive None or []. These arguments do not become calculation parameters;
clients must supply discovered semantic refs in bindings, not raw column names in
params. Resolved arguments are recorded in `python.resolved_inputs`. Multiple tables
cannot both supply one function argument. Fixed-column functions may omit column_args.

For the smallest complete example see examples/methods/authoring/column_arguments.py
and the write_your_method notebooks. They compare direct Python with governed
execution, test refusals and exercise the default matching/OLS Methods. In Web, use
the Method's input-selection/test link and result preview; saving a Recipe is not
required. Preview executes the installed/published code, not an editor draft.

Keep imports, ordinary calculation, optional checks/output conversion, then METHOD
registration. Use `analyze(data)` for one table, or named tables for multiple periods.
`manifest.data_inputs` is the executable contract returned by describe_method. Explain
what one row means and bind required aliases to discovered objects before running.
If the user has not chosen among semantically different outcomes or dates, ask;
matching types/names do not establish business meaning.

Entity analyses can optionally use `DataInput(columns={...})` with existing RoleSpec
for measure-or-dimension variables and multiple covariates. Multiple bindings become
`confounders_0`, `confounders_1`, etc.; the entity key is `unit`. The Run records actual
aliases/references as `python.resolved_inputs`. Calculation options remain separate.
DoWhy matching/regression 1.1.0 use this path; pinned 1.0.0 is retained. Source-aware
time adapters remain advanced cases, never mandatory contributor boilerplate.
`calculation/InputTable` is a legacy API, not a second beginner template.

## Skill file
Use a directory containing only reviewed Markdown assets (all *.md are loaded):
```yaml
---
name: team.metric_review
version: 1.0.0
description: 공식 지표를 확인하고 해석의 한계를 설명합니다.
suggested_methods: [analysis.metric_lookup]
---
```
Then describe when to use it, required user decisions, existing tools, stop conditions and interpretation limits. Do not copy Cube definitions. `describe_method` returns the guide. Start with `start_analysis(..., guide="team.metric_review")`; the Run snapshots its version, hash and text. Execute registered tools with run_step; only those results are evidence. The guide's recommendations are not automatically enforced or replayed. Use a Recipe for deterministic replay.

## Write the analysis procedure

A query-executing Skill needs name, version, description and `query_execution: true`
in its YAML header. Omit roles and parameters to use the shared query inputs:
metric (required), related metrics and suggested dimensions (optional), filters,
population and an optional comparison period. Explicit role/parameter maps still
define the full respective contract, including empty maps. The server enforces
bound metrics and scope; Markdown never grants permissions. Write the body as an
analyst would explain the procedure:

1. Break down revenue by product department.
2. Choose the highest-revenue department. Ask the user when first place is tied.
3. Continue by store within the selected department.
4. Explain the observed values and any missing data; do not claim a cause.

Do not copy tool calls, Run/step IDs, pagination or filter propagation into each
Skill. The product automatically supplies and snapshots the shared `analysis-core`
guide beside the individual procedure when a Skill starts. The client AI uses it
to discover semantic objects, execute scoped queries, inspect evidence and complete
the step. Read it with `get_method_guide("analysis-core")` when developing a client.
The server still enforces access, scope, query limits and evidence references.
Reading either guide alone is not validation. No server LLM runs in the background.

## Calculation checks

Keep the calculation and its registration in `method.py`. Put longer data and
analysis checks in `checks.py` and reference them using `checks=[check_data]`.
A check can receive its DataFrame and named column arguments, just like the
calculation. Existing DataFrame-only checks continue to work. The server records
failed checks and stops before calculation. Test both successful and invalid data
in `test_method.py`; importing a check does not replace executing it.

## Operate owned assets
Deploy the reviewed project and dependencies and set `DL_PROJECT_DIR` to the directory
containing `decision-layer.yaml`. Startup, CLI and local Python share its loader.
Use Git review, tests and version bumps; restart after deployment. Legacy installed
modules exporting METHODS via DL_METHOD_MODULES and standalone DL_SKILLS_DIR remain
compatible. Duplicate names fail startup. The operator-enabled Web editor continues
to publish managed versions separately. Registration checks do not prove analytical
quality. Pin dependencies and retain released environments.

Local MethodSession trials execute in process. Server functions/checks/adapters must be importable top-level module functions and run in a bounded process. This is not a security sandbox: reviewed Python can access its host/network. Shared deployment remains disabled; do not install untrusted code. Function hashes are best-effort source fingerprints, not a trace of library internals, closure state, all data access or a reproducible environment. Preserve the package/environment separately.

Legacy async/class Methods and calculation adapters still run. Use them for explicit source pushdown and advanced execution contracts; no bulk migration is required. Releasing changed logic requires a new Method version. Historical Run snapshots stay immutable; rerunning with a new implementation requires review and a new execution.

## Python formatting and review

Use the same style in ordinary modules, notebooks and Web: Ruff 0.12.3, 88 columns,
four spaces, double quotes. Keep imports, calculation, optional checks/output adapters,
and METHOD registration in that order. Legacy modules may still export METHODS. Omit sections you do not need; the formatter
does not require a Method class or alter your calculation API. Optional library imports
can stay inside the calculation so discovery does not require statistical extras.

Run `make format-methods` and `make check-method-format` for the current contribution
examples; for your module run `ruff format path/to/method.py` with repository config.
Web's code-format action parses text without importing it, changes only the editor,
and can be undone. Review the added/deleted lines, then save/check/publish explicitly.
Formatting never counts as analytical validation. Full Run source snapshots and hashes
remain exact; the authoring projection uses the common formatter.
