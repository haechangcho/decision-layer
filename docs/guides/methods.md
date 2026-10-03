# Add a Method

A Method is one analytical capability. If existing capabilities cover the calculation, contribute a Recipe instead. Start with the business question and the claim the analysis can legitimately support.

## Extension model

Methods are reviewed Python implementations installed with the server. There is no dynamic plugin installer or user-uploaded executor. A manifest describes the contract, not the calculation. MCP exposes registered Methods, not a separate execution engine or Claude Skill runtime.

Read the working examples:

- [Base contract and registry](../../src/decision_layer/methods/base.py).
- [Execution context](../../src/decision_layer/methods/context.py).
- [Trend implementation](../../src/decision_layer/methods/query/trend.py).
- [Typed models](../../src/decision_layer/core/models.py).
- [Tests and fake provider](../../tests/unit/test_methods.py).

## Implement

1. Add a module under the appropriate family in `src/decision_layer/methods/`.
2. Subclass `Method`. Define a `MethodManifest` with name, version, description, typed roles, parameters, execution mode, interpretation and output types.
3. Implement `async run(ctx, bindings, params) -> MethodOutput`. Request required columns and grain through `ctx.dataset(DatasetSpec(...))` to preserve budgets and provenance.
4. Return a primary artifact, supporting artifacts, validation and warnings. Refuse when required assumptions or capabilities are missing.
5. Register with `registry.register(...)` and import the module in [methods/__init__.py](../../src/decision_layer/methods/__init__.py).
6. Use existing localization helpers and add Korean user-facing messages in [ko.json](../../src/decision_layer/i18n/ko.json).

Keep metric SQL, joins and access semantics in Cube. Do not bypass the context with raw source queries. Methods must work through the canonical API, not only a Web screen.

## Validate and document

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
.venv/bin/pytest
```

Follow [Testing](testing.md) for integration checks. Where Chinook supports the question, add a reviewed [reference case](../../examples/chinook/evals/cases.json) with independent SQL and an expected value. Do not use the Method's own output as its reference. Causal Methods need suitable data and assumptions; this music-store sample does not establish causal effects.

## Recipes

Use the [music-sales template](../../examples/chinook/templates/music-sales.yaml) as a complete example. Reference existing Methods and semantic objects, validate against the sample and explain the question and steps. Do not embed semantic SQL. Keep optional templates separate from the initially empty runtime Recipe folder.

Downloadable plugins, external Method catalogs and compatibility negotiation would need a separate design and security decision. They are not prerequisites for contributing today.
