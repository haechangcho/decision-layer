# Add a Method

A Method is one analytical capability. If existing capabilities cover the calculation, contribute a Recipe instead. Start with the business question and the claim the analysis can legitimately support.

## Extension model

### Declarative editor inputs

Give a role a `label` and `default_binding="primary_metric"` to inherit the Recipe metric.
Only required roles and basic parameters appear in ordinary step editing. Optional
bindings and technical settings remain available through the complete Recipe code view.
A multi-value role may declare `editor_parameter` pointing to a matching scalar
semantic parameter. Drilldown uses this to expose only the effective dimension for
this step while retaining the stored dimension list. Do not infer this relationship
from parameter names; the manifest validates it explicitly.
Declare `requires_period=True` when a Method needs a scoped period; the editor asks
for it only after the user chooses to check the result. A period-dependent boolean
can declare `meaning="period"`. Do not add Method-name branches to the frontend.
Parameters declare `type`, `label`, `required`, bounds and `ui_group` (`basic`, `options`,
`hidden`; `advanced` remains compatible). Explicit hidden values remain inspectable.
`semantic_kind` makes a string/ref-list input a catalog picker. `visible_when` can
depend on a declared parameter. These metadata generate the shared editor, not custom UI code.

Optional scalar roles with the same `exclusive_group` appear as one alternative-field
picker; a valid Recipe selects exactly one. Basic `group` parameters use `semantic_role`
to appear beside their criterion, with typed boolean, value-list, exclusion and numeric
range controls. Changing the criterion resets unfixed group definitions, not hidden
validation thresholds. Use these contracts rather than contributing a custom UI panel.

A native average can declare a count role with `default_binding="unit_count"`.
`configure_step(..., catalog=catalog)` writes an explicit binding only when the visible
catalog declares exactly one native row count on that average's primary unit. REST
configuration uses the current caller's catalog. No candidate or multiple candidates
require input; existing choices are preserved. Per-unit runtime validation still applies.

Group inputs can declare `InputSourcePolicy(allowed=["literal", "step", "input"],
default="previous_result", project="condition")`. This selects the first ranked group
from the most recent earlier capable step. `parameter_parents` derives a comparison
population from another parameter's step source. Missing required targets become
typed runtime inputs without a remembered value. `configure_step(recipe, index)` and
`POST /recipes:configure-step` produce the same explicit spec; execution remains subject
to the existing completeness, ambiguity and access checks. Statistical/ML code still
runs in a reviewed Python Method, never in manifest expressions or frontend plugins.

Methods are reviewed Python implementations installed with the server. There is no dynamic plugin installer or user-uploaded executor. A manifest describes the contract, not the calculation. MCP exposes registered Methods, not a separate execution engine or Claude Skill runtime.

Read the working examples:

- [Minimal Method and executable contract tests](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_method_contribution.py). The example uses an isolated registry; it is not installed as a production Method.

- [Base contract and registry](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/base.py).
- [Execution context](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/context.py).
- [Trend implementation](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/query/trend.py).
- [Typed models](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/core/models.py).
- [Tests and fake provider](https://github.com/haechangcho/decision-layer/blob/main/tests/unit/test_methods.py).

## Implement

1. Add a module under the appropriate family in `src/decision_layer/methods/`.
2. Subclass `Method`. Define a `MethodManifest` with name, version, description, typed roles, parameters, execution mode, interpretation and output types.
3. Implement `async run(ctx, bindings, params) -> MethodOutput`. Request required columns and grain through `ctx.dataset(DatasetSpec(...))` to preserve budgets and provenance.
4. Return a primary artifact, supporting artifacts, validation and warnings. Refuse when required assumptions or capabilities are missing.
5. Register with `registry.register(...)` and import the module in [methods/__init__.py](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/methods/__init__.py).
6. Use existing localization helpers and add Korean user-facing messages in [ko.json](https://github.com/haechangcho/decision-layer/blob/main/src/decision_layer/i18n/ko.json).

Keep metric SQL, joins and access semantics in the connected semantic layer. Do not bypass the context with raw source queries. Methods must work through the canonical API, not only a Web screen.

## Declare Result Capabilities

Declare stable `provides` names in the Method manifest, for example `metric_lookup` or
`matched_comparison`. Recipe candidates and Run goal evidence use these declarations,
not the Method's display name. For parameter-dependent output, `provides_when` maps a
capability to parameter names (any truthy parameter enables it). Return `MethodOutput`
with explicit `provides` when runtime validation changes the available capabilities.
Results may only expose declared capabilities; refused results expose none. Add tests
showing both sufficient and insufficient inputs, not only successful calculations.

Do not declare causal or inferential capability for a descriptive aggregate lookup.

## Validate And Document

| Part | Evidence |
| --- | --- |
| Question | Why existing Methods are insufficient |
| Manifest | Roles, defaults, bounds, outputs and interpretation |
| Data | Grain and required provider capabilities |
| Validation | Missing data, invalid parameters, small samples and unsupported assumptions |
| Result | Known values, warnings, refusal and provenance |
| Example | Invocation, expected result and unsupported claims |
| Compatibility | Impact on existing Recipes and Method versions |

Add focused tests for valid inputs, missing roles, invalid parameters, empty data and interpretation limits. Prefer deterministic provider fixtures for calculations; use live tests for Cube-dependent behavior.

```bash
.venv/bin/pytest tests/unit/test_methods.py
.venv/bin/pytest tests/unit/test_method_contribution.py tests/unit/test_causal.py
.venv/bin/pytest
```

Follow [Testing](testing.md) for integration checks. Where Complete Journey supports the question, extend its [independent SQL verifier](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/verify.py) and [live MCP test](https://github.com/haechangcho/decision-layer/blob/main/tests/provider/test_complete_journey_live.py). Do not use the Method's own output as its reference. Causal Methods need suitable data and assumptions; this observational sample does not establish causal effects. Keep deterministic statistical and causal contract tests independent of the live dataset.

## Recipes

Start with a recorded analysis in the Complete Journey sample. Review its question, steps, settings and queries, then register the completed procedure as a Recipe. To change it first, choose Edit before saving and review the draft in the editor. Both paths preserve the recorded settings, scope and Method versions. Reference existing Methods and semantic objects; explain the question and steps without embedding semantic SQL. Export the reviewed YAML for a contribution. Keep optional templates separate from the initially empty runtime Recipe folder.

Downloadable plugins, external Method catalogs and compatibility negotiation would need a separate design and security decision. They are not prerequisites for contributing today.

Reviewed Methods may use statistical or ML libraries. Declare dependencies, keep extraction governed and bounded,
and include library versions through `MethodOutput(runtime=...)`. Heavy optional dependencies should fail with
an actionable message when not installed, not trigger runtime installation. Validate model assumptions and
interpretation; using a library does not itself justify a causal claim.

## Average-outcome CEM

`causal.cem@1.1.0` accepts an explicit `sample_count` for native averages. Both references must have the
same provider-declared queryable primary key. A bounded query verifies one counted row and one finite,
non-null outcome per unique unit. This does not infer sample semantics from neighboring metrics or
accept arbitrary SQL. Unknown contracts refuse; hosted dbt API metadata currently cannot establish this path.
Results carry `statistical_judgement: not_tested`: continuous-outcome uncertainty is not implemented,
and an average is never passed into a percentage/proportion significance test.
The [campaign example](https://github.com/haechangcho/decision-layer/blob/main/examples/complete-journey/CAMPAIGN_ANALYSIS.md)
demonstrates Cube results and insufficient-overlap refusal, not causal ground truth.

## CEM Review Scenarios

`causal.cem@1.1.1` tightens range and inference checks. Existing pinned Recipes require
review before upgrading; historical Runs remain unchanged.

- Compare two populations with different condition mixes but identical within-condition outcomes. Matching must remove the composition-only difference.
- Verify target-composition weights against hand-calculated values, not the Method's own result.
- Test absent common strata, low retention, insufficient counts and missing conditions. Failed comparisons expose no supported capability or significance artifact.
- Reject overlapping groups, reversed/duplicate/non-finite edges and ranges on unselected or nonnumeric conditions before querying.
- Never infer a percentage from values in 0..100. Intervals require declared count numerator/denominator and a same-scope check of the actual counts and percentage scale. Unknown definitions and fraction-scale outputs do not receive percentage intervals.
- Test native averages with missing counts, duplicate units and null outcomes. Continuous-outcome inference remains unsupported.
- Record that post-match balance concerns the coarsened strata, not exact equality within numeric bins. Covariate timing and independent sampling require analytical review; this implementation does not establish them.

The contribution contract tests cover valid execution, invalid inputs, empty results,
query limits and provenance. Extend them with a Method-specific independent reference,
provider compatibility checks and an editor test when declaring a new input type.
