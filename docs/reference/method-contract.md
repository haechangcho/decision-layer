# Method contract

Use this page when declaring inputs, outputs or editor behavior.
For an executable walkthrough, start with [First Method](../guides/methods.md).

## Implementation and registration

A Method is reviewed Python code installed with the server. Its manifest describes
the contract; `run()` implements the calculation. There is no dynamic installer or
code-upload executor. Web, Python, REST and MCP use the same contracts.

1. Add a `Method` subclass under `src/decision_layer/methods/`.
2. Declare its name, version, roles, parameters, execution mode, interpretation and artifact types in `MethodManifest`.
3. Implement `async run(ctx, bindings, params) -> MethodOutput`.
4. Fetch required columns and grain through `ctx.dataset(DatasetSpec(...))`.
5. Add the implementation to `register_builtins()` in `methods/__init__.py`. Modules do not register themselves on import.
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

- [First Method](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/first_method) and [multi-query peer comparison](https://github.com/haechangcho/decision-layer/tree/main/examples/methods/peer_comparison)
- [Method base](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/base.py), [Registry](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/registry.py) and [execution context](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/context.py)
- [Typed models](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/core/models.py) and [contract tests](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_method_contribution.py)
- [Testing](../guides/testing.md) and [contribution workflow](https://github.com/haechangcho/decision-layer/blob/main/CONTRIBUTING.md)
