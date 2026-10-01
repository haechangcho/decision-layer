# Decision Layer — Agent Instructions

## What this repository is

Decision Layer is an open-source analytics knowledge and execution layer for semantic layers.

It connects governed semantic models (Cube first) to reusable analytical methods and organization-specific analysis recipes, and exposes the same execution model through Web UI, Python, REST, and MCP.

The product is not a BI tool, notebook, semantic layer, scheduler, or decision-graph product.

## Read before making architecture or product changes

Always read these files before proposing or implementing non-trivial changes:

- `docs/PRODUCT_CONTEXT.md`
- `docs/ARCHITECTURE.md`
- `docs/DECISIONS.md`

When available locally, also read `docs/REFERENCES.md` and `docs/MVP_PLAN.md`.
Internal research, design proposals and milestone checklists are local working
documents and are not required to contribute to the public repository.

Treat those documents as the current source of truth.

If implementation reality conflicts with them, do not silently diverge. Explain the conflict and update `docs/DECISIONS.md` when an architectural decision changes.

## Core principles

1. **Semantic layer owns what data means.**
   - Metric definitions, dimensions, entities, joins, grain, access semantics, and canonical business definitions belong to the semantic provider.
   - Decision Layer references semantic objects; it does not redefine them.

2. **Decision Layer owns how data is analyzed.**
   - Analytical procedures, methods, validation, execution, provenance, and reusable analyst workflows belong to Decision Layer.

3. **Method != Recipe.**
   - A Method is an atomic analytical capability such as drill-down, OLS, CEM, or DiD.
   - A Recipe is reusable procedural knowledge describing how an analyst investigates a recurring business question.

4. **Prefer typed executable specifications over free-form instructions.**
   - Free-form context may supplement a Recipe, but must not override semantic definitions or core validation.

5. **Cube is the first-class semantic provider for MVP.**
   - Build one excellent integration before broad provider coverage.
   - Keep provider contracts generic enough for future MetricFlow/dbt/Malloy/etc.

6. **All product surfaces share the same execution model.**
   - Web, Python, REST, CLI, and MCP must create or execute the same canonical specs.
   - Do not implement separate logic per interface.

7. **The agent must not invent analytical code.**
   - Natural language is mapped to registered Methods/Recipes and existing semantic objects.
   - LLMs may plan and narrate, but execution must run through governed contracts.

8. **Provenance and validation are first-class.**
   - Every result should be inspectable: source, semantic references, recipe/method versions, queries/specs, freshness, warnings, and validation status.

9. **Push work down when possible.**
   - Aggregation and filtering should remain in Cube/warehouse when possible.
   - Entity-level/statistical workloads should only materialize the columns and grain required by the Method.

10. **Do not overbuild.**
    - Trigger/scheduler engines, notebook products, full workflow DAG engines, Decision Graph, BI/dashboard builders, and custom frontend plugin runtimes are not MVP requirements.

11. **Challenge product assumptions.**
    - Do not blindly preserve ideas because they were discussed.
    - Prefer smaller abstractions backed by concrete use cases.
    - Flag premature abstractions.

12. **A wrong analytical answer is worse than no answer.**
    - Fail closed when assumptions or required data are missing.
    - Distinguish association, decomposition, descriptive analysis, and causal claims.

## Current product thesis

The strongest near-term use case is not “a GUI for CEM/DiD.”

The product should make **organizational analytical procedures executable and reusable**:

> A senior analyst can encode “when revenue changes, compare periods, break it down by product/region/customer, inspect quantity/unit price/discount, and then investigate the dominant branch,” and the same procedure can be executed consistently by analysts and AI agents against the governed semantic layer.

Statistical and causal Methods (OLS, CEM, DiD) are reusable primitives within this system.

## Development behavior

Before implementing a large feature:

1. Identify which core object it belongs to.
2. Check whether an existing abstraction already covers it.
3. Verify that it does not leak semantic definitions into Recipe/Method code.
4. Verify that it works through the canonical API, not only the Web UI.
5. Add or update tests.
6. Update `docs/DECISIONS.md` if the architecture changes.

When asked to “add a new analysis,” decide whether it is:
- a new **Method**,
- a new **Recipe** composed from existing Methods,
- a new **Validator**,
- or merely a new configuration of an existing Recipe.

Do not create a new Method when a Recipe is sufficient.
