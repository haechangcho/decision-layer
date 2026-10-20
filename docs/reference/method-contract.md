# Method contract

Use this page when declaring inputs, outputs or editor behavior.
Start with [Understand Methods](../guides/methods.md) or the [Python function example](../tutorials/write-your-method).


## Register an ordinary Python function

Use `python_method(function, name=..., version=..., inputs=...)`.
`inputs` maps each DataFrame argument to a `DataInput`. Export the resulting
object as `METHOD` in the project's `method.py`.

| Declaration | Meaning |
|---|---|
| `Column(source="measure")` | Metric |
| `Column(source="dimension")` | Dimension |
| `Column(source=["measure", "dimension"])` | Either semantic kind |
| `Column(source="dimension", role="entity_key")` | A key identifying each row, such as customer or order ID |
| `Column(..., dtype="number")` | Numeric values only |
| `Column(..., multiple=True)` | Several variables |
| `DataInput(..., minimum_rows=10)` | Minimum row count |

Function arguments matching declared columns receive resolved DataFrame column names.
Ordinary options are inferred from the function's types and defaults. `output="auto"`
adapts tables and estimates; `table` or `estimate` requires one result shape. Shared
code checks inputs and data requirements. Add analysis-specific checks with
`checks=[check_function]`.

See [Connect a Python function](../tutorials/write-your-method) for registration and execution.

## Function authoring API and internal contract

For advanced control over queries, use `@method(...)` with typed keyword arguments: `Measure`, `Dimension`, `TimeDimension`, `Entity`, `DateRange`, `Equality`, `list[Filter]`. Roles, ordinary parameters and output types generate the existing `MethodManifest`. `requires_packages` declares installed-version checks, not runtime installation. Unsupported annotations fail before registration.

- `ctx.aggregate(...)`: provider aggregates, with explicit top-N or bounded complete extraction.
- `ctx.entities(...)`: complete observations at a declared primary unit, keyed by unit × time when bucketed.
- `ctx.compute(fn, ...)`: pure computation without credentials, in-process for direct trials and terminable children for server/preview.
- `Table`, `Estimate`: JSON-compatible artifacts with finite-value and payload-shape checks.

`Table.from_dataset(data)` preserves the row list in `primary.data` and semantic
column metadata in `primary.columns`: alias, reference, role and time granularity.
Grouped queries and monthly trends use the same return type. Web renders a trend
for one bucketed time column and measures without additional grouping/entity columns;
other results remain tables. Date-looking strings in `Table(rows)` are not inferred
as time axes. Existing `TimeSeries` Methods and stored `time_series` artifacts remain
supported for compatibility. Analytical capabilities such as `time_series` are
independent of the artifact's presentation type.

New Methods declare `interpretation="association"` for observational summaries
and relationships: grouped queries, trends and regression associations all belong
to this level. It does not establish a causal effect. `causal_conditional` retains
its assumption-dependent contract. Legacy `descriptive` and `associational` values
remain readable and executable; stored labels and installed builtin versions are
not rewritten. Association goals can reuse either legacy noncausal result when
their required capabilities and semantic references match. Legacy goal rules stay
unchanged; migrate them explicitly when changing an existing Recipe contract.

Python and REST/MCP measure/dimension/entity maps normalize into canonical bindings. REST uses `POST /methods/{name}:run` or `POST /runs/{id}/steps`. Recipe steps store canonical bindings/params; legacy bindings remain accepted. Web displays the same manifest roles and structured parameters and contains no separate analytical implementation.

Advanced variable roles can explicitly accept measures and dimensions (`accepted_kinds`). `Entity` must reference a provider-declared primary dimension. Objects inside conditions/filters also undergo catalog/access checks. Mandatory scope filters cannot be removed; current queries cannot expand Run dates. Comparisons use an explicit policy path.

Default complete extraction limits are 50,000 rows, 100 selected aliases and two million cells; smaller server policy row limits take precedence. A sentinel row detects truncation instead of accepting partial samples. Statistical encoding also limits 100 columns / two million cells. Bounded filter/window lists (30), query budgets/deadlines and attempt recording apply. Cross-query warehouse snapshot consistency is not guaranteed.

Results record versions, canonical specs, attempts/labels, installed required-library versions, Python, validation and warnings. Arbitrary class artifact payloads still need independent tests. See the [Python function example](../tutorials/write-your-method) for the basic flow.

The class API below remains the extension path for additional artifacts, selections and specialized contracts. Simple Methods need no duplicate manual manifest declaration.

## Implementation and registration

A Method is reviewed Python code installed with the server. Its manifest describes
the contract; `run()` implements the calculation. There is no dynamic installer or
code-upload executor. Web, Python, REST and MCP use the same contracts.

1. Add a `Method` subclass under `src/decision_layer/methods/`.
2. Declare its name, version, roles, parameters, execution mode, interpretation and artifact types in `MethodManifest`.
3. Implement `async run(ctx, bindings, params) -> MethodOutput`.
4. Fetch required columns and grain through `ctx.dataset(DatasetSpec(...))`.
5. Add the implementation to `register_builtins()` in `methods/catalog.py`. Modules do not register themselves on import.
6. Add independent answer and failure tests. Use localization helpers and add Korean user-facing messages in `i18n/ko.json`.

Keep metric formulas, joins and permissions in the semantic provider. Do not bypass
the execution context with raw queries. A Method may combine several datasets.
Use a [Recipe](../guides/recipes.md) when existing Methods cover the calculation.

## Inputs and editor metadata

| Declaration | Behavior |
| --- | --- |
| Role `label`, `default_binding="primary_metric"` | Display a role and inherit the Recipe metric |
| Role `exclusive_group` | Offer alternative scalar roles; a valid Recipe selects exactly one |
| Role `editor_parameter` | Connect a multi-value role to the scalar semantic input used by this step |
| Parameter `type`, `required`, bounds | Validate values |
| Parameter `label`, `ui_group` | Group editor controls as `basic`, `options` or `hidden`; `advanced` remains compatible |
| Parameter `semantic_kind` | Select catalog objects |
| Parameter `visible_when` | Show a control based on another declared parameter |
| Group parameter `semantic_role` | Place group controls beside their semantic criterion |
| Manifest `requires_period=True` | Require a scoped period when checking a result |
| Boolean parameter `meaning="period"` | Identify an option that enables a period-dependent calculation |

Ordinary step editing shows required roles, alternative roles, existing bindings and
basic parameters. Other bindings and technical settings remain available in Recipe
code. Explicit hidden values remain inspectable. Changing a group criterion resets
unfixed group definitions, not validation thresholds. Do not add Method-name branches
or custom frontend panels for these inputs.

A native average may declare a count role with `default_binding="unit_count"`.
`configure_step(..., catalog=catalog)` writes a binding only when the caller's catalog
declares exactly one native row count on the same primary unit. Otherwise input is
required; existing choices remain. Runtime unit checks still apply.

## Input sources

Group inputs can declare:

```python
InputSourcePolicy(
    allowed=["literal", "step", "input"],
    default="previous_result",
    project="condition",
)
```

`previous_result` selects the first ranked group from the most recent earlier capable
step. `parameter_parents` derives the comparison population from another parameter's
step source. Missing required targets become typed runtime inputs without remembered
values. Python `configure_step(recipe, index)` and REST `POST /recipes:configure-step`
create the same explicit spec. Execution checks completeness, ambiguity and access.
Manifest expressions and frontend plugins do not contain analytical code.

## Outputs and capabilities

Return a primary artifact, supporting artifacts, validation and warnings through
`MethodOutput`. Declare every emitted artifact type. Registry checks reject undeclared
artifact types, selections and capabilities; Method tests verify payloads and numbers.

Declare stable capability names in manifest `provides`, such as `metric_lookup` or
`matched_comparison`. Recipe candidates and Run goals use these names, not display
labels. `provides_when` maps a capability to parameter names; any truthy parameter
enables it. Return explicit `MethodOutput.provides` when runtime validation changes
which capabilities are available. Refused results expose none.

A descriptive lookup must not declare causal or inferential capability.
Statistical/ML libraries require declared dependencies, bounded extraction and version
evidence in `MethodOutput(runtime=...)`. Missing optional libraries should give an
actionable error, not install themselves at runtime.

## Validation and compatibility

Test independently known values, missing roles, invalid parameters, empty data,
query limits, provenance and interpretation limits. Use strict query fixtures for
calculations and live tests for provider behavior. Do not use the Method's output as
its own reference. New input types also need editor tests.

Document why existing Methods are insufficient, required grain/provider capabilities,
unsupported assumptions, warnings and the impact on pinned Recipes. Historical Runs
remain unchanged; review pinned versions before upgrading.

```bash
.venv/bin/python -m pytest -q examples/methods
.venv/bin/python -m pytest -q tests/unit/test_method_contribution.py tests/unit/test_causal.py
make test
```

For CEM, test composition-only differences, independently calculated weights,
common-strata coverage, retention, sample counts, overlapping groups and invalid bins.
A native average requires declared sample counts, a shared queryable primary key and
one finite non-null outcome per unique unit. Hosted dbt metadata currently cannot
establish that path. Continuous-outcome inference remains unsupported.

Percentage inference requires declared count numerator/denominator and verified
same-scope counts and scale. Never infer percentage semantics from values alone.
Matched balance concerns coarsened strata; covariate timing, independent sampling and
causal identification require separate review. See the [CEM tests](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_causal.py).

## Code references

- [Python Method project](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/project) and [SDK contract fixtures](https://github.com/haechangcho/decision-layer/blob/main/tests/support/methods/functions.py)
- [Method base](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/base.py), [Registry](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/registry.py) and [execution context](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/context.py)
- [Typed models](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/core/models.py) and [contract tests](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_method_contribution.py)
- [Testing](../guides/development.md) and [contribution workflow](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)

## Transition existing implementations

Existing class Methods, bindings, registration and Recipe versions remain valid. Move simple Methods to typed functions, verify equivalent calculation with independent full-spec fixtures, then deploy a new version. Classes needing extra artifacts/selections can stay. Update Recipe pins after review; never rewrite historical Runs. Choose core or required extras for the server, and apply Cube observation-key/panel changes separately from API deployment. No DB migration is needed.

New Python authors pass named function arguments directly. Roles/parameters are internal semantic-reference and ordinary-value validation categories. `AnalysisDesign` parsing is retained only for legacy serialized Method contracts; current authoring examples do not use it. See ADR-084.

## Discovery and authoring defaults

`@method(name, version=...)` defaults to `association`. The signature supplies types and the docstring supplies the description; purpose is not inferred from code. `provides` is optional, but explicit result assertions still govern Recipe and goal evidence. See [the Method overview](../guides/methods.md). `POST /methods:search` uses `MethodSearchRequest` (`goal`, optional `names`) and never executes analytical queries.
