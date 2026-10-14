# Write Methods that people and AI can choose

Start with the [first Method](methods.md), then inspect its registered contract.
The APIs below are implemented and covered by executable tests. Natural-language
understanding remains the AI client's responsibility; this is not an automatic router.

## What changed

Previously, a function without a docstring appeared under its name alone. MCP offered
names and role summaries, then told the AI to use CEM for factor relationships and a
fixed sequence for change questions. Neither rule compared the actual candidates.
`provides` accepted a string accidentally as a sequence of individual characters.

The existing authoring API already derives the description from a docstring and the
inputs and outputs from the signature. We retain that path and now default
observational interpretation to `association`. New examples
explain their purpose in one docstring. Old functions without descriptions still run;
discovery marks `description_available=false` so absence is not treated as meaningful
information. A docstring is authored guidance, not a verified statement about the code.

`find_methods` uses the same input checks as execution to inspect types, required
provider features and installed package versions. It returns candidates, excluded
Methods with reasons, and the actual registered capability names. It neither executes
a query nor chooses the first candidate. The MCP-specific analytical playbooks were
removed; investigation order belongs in Recipes.

## Before and after

Before, this Method needed an explicit observational label but supplied no explanation:

```python
@method("example.group_metric", version="1.0.0", interpretation="association")
async def group_metric(ctx, *, metric: Measure, group: Dimension,
                       limit: int = 5) -> Table:
    data = await ctx.aggregate(measures={"metric": metric}, dimensions={"group": group},
                               order=[(metric, "desc")], limit=limit)
    return Table.from_dataset(data)
```

The current executable implementation adds bounds and explains its purpose once:

<<< @/../examples/methods/patterns/methods.py#group_metric

No separate description, input schema, output schema, search tags or capability list
is needed for this local Method. The annotation describes the input type, not its
business meaning: a measure can still be the wrong outcome for the question.

## Register, inspect, execute and test

Run the complete Python example from the repository root:

```bash
.venv/bin/python -m examples.methods.patterns.discovery
.venv/bin/python -m pytest tests/unit/test_method_discovery.py
```

The example registers the same `group_metric` implementation, inspects it, executes
one strict fixture query and returns A=30, B=20, C=10. Discovery consumes no query.
The workshop notebooks also inspect the Method they just authored with:

```python
method_choices = group_session.find_methods()
```

`MethodSession` is local development infrastructure. Production still installs reviewed
Python and registers Methods at server startup. MCP sends names and inputs to that
server; it does not upload Python or register a new function on every question.

To inspect an explicit analytical goal, use the existing `AnalysisGoal` contract:

```python
from decision_layer.core.models import AnalysisGoal

report = session.find_methods(goal=AnalysisGoal(
    id="lookup", description="Show the requested measure by group",
    semantic_refs=[M, GROUP], required_capabilities=["metric_lookup"],
    interpretation="association",
))
```

This fragment assumes the session and references from `patterns/discovery.py`.
The capability name is copied from the registered contract for governed lookup. Do
not invent a tag for an unsupported question or choose a tag merely because it yields
a candidate. An empty list makes no assertion about analytical purpose.

The same request is served by `POST /methods:search` with `{"goal": ...}`. MCP's
`find_methods(goal=...)` delegates to it and restricts names to its configured profile.
The Web Method detail page's requirement check uses the same endpoint with
`{"names": [method_name]}`. All execution continues through the existing Registry and
RunEngine; discovery does not authorize execution or reserve a query budget.

## Which settings remain necessary?

| Information | Decision and reason | If omitted |
| --- | --- | --- |
| Name and version | Keep explicit: registration, Recipe references and provenance | Required |
| Input types and defaults | Derive from the signature; validate values through the shared Registry | Missing required inputs fail before queries |
| Description | Use the docstring once; do not infer analytical intent from the body | Legacy name fallback; discovery flags missing explanation |
| `interpretation` | Default to `association`; stronger claims require explicit declaration and analytical checks | Association, not causal identification |
| `provides` | Keep optional for reusable **result assertions**, not search keywords | Empty; no capability is asserted or inferred from `Table` |
| `provides_when` | Keep advanced class contracts: capability may require comparison options | Unconditional assertions only |
| `requires_packages` | Keep version checks before queries and versions in provenance; reject invalid specifiers at function definition | No declared package preflight |
| `requires_period` | Keep when analysis cannot run without dates; scope policy still applies independently | False; no special Method period requirement |
| `kind`, `execution` | Retain metadata and legacy compatibility; do not use as evidence of purpose or a compute sandbox | Existing `query` / `semantic_pushdown` metadata defaults |
| Provider requirements | Infer entity-query support from an `Entity` input; retain specialized class declarations | No extra provider feature requirement |
| Editor labels, groups and source policies | Keep for existing Recipe editing and dynamic inputs, outside the simple authoring path | Generic generated controls |
| Selection output names | Keep for typed references between Recipe steps, validated against declared outputs | No selections |
| Legacy `AnalysisDesign`, `TimeSeries`, old interpretations | Compatibility only; do not require them in new tutorials | New examples use ordinary inputs, Table/Estimate and association |

`provides` is not removed because Recipe routing and evidence completion consume its
exact values. It is also not inferred from return type or arbitrary Python query code.
New function declarations reject prose, empty names, duplicates and a scalar string.
Custom names remain possible: their author must document and test the asserted result.
Discovery exposes a dynamic `capabilities` map of names to installed Methods and reports
unknown requested names explicitly. This avoids a second universal taxonomy while
preserving extension and historical contracts. Syntactic validation cannot detect a
plausible but semantically wrong capability declaration.

Other ambiguous behavior was fixed: an optional union such as `int | str | None` no
longer silently advertises only one type. Unsupported unions fail at definition time.
Nonpublic objects now fail at the execution-context boundary as well as discovery.

## How selection works

With a Recipe: resolve semantic objects and goals, call `find_recipes`, inspect its
procedure, fixed settings and coverage, then execute a suitable Recipe. Existing
selection/rejection evidence and Recipe allow-lists still apply. Discovery cannot add a
Method to a Recipe's allowed execution set.

Without a suitable Recipe: inspect `find_methods`, compare descriptions and interpretation,
resolve the intended variable roles and comparison, then supply the canonical inputs.
If several candidates answer different questions, clarify the intended question. If none
fits, report that part as unsupported rather than substituting a simpler analysis.

The server checks declared capability coverage, interpretation, visible input types,
provider features and installed versions. Candidate input references are type-compatible
options from the supplied goal, **not inferred bindings**. Actual periods, values, query
joins, grain, extraction limits and analytical diagnostics are checked at execution.
Description relevance, confounder selection and identification assumptions need domain
judgment. No tool response claims these have been proved.

## Verified scenarios and limits

| Question scenario | Deterministic test | Human/AI decision still needed |
| --- | --- | --- |
| Show a measure by group | Explicit `metric_lookup` returns aggregate; typed refs are offered | Correct measure and grouping meaning |
| “Analyze this” | No capability restriction leaves multiple candidates | Ask what result or comparison is wanted |
| Several plausible Methods | Candidate list is retained; no score picks a winner | Compare estimands, assumptions and purpose |
| Forecast future sales | Unknown forecast capability returns no candidate and names the unsupported requirement | Explain registered support; do not relabel as lookup |
| Causal request with an association-only Method | Interpretation mismatch excludes it | Causal identification still requires evidence |
| Missing package or entity-query support | Excluded with a concrete reason before data queries | Install a reviewed environment or choose an appropriate supported approach |
| Hidden semantic input | Same access error at discovery and execution, no row query | Obtain access through the provider |
| Comparison capability needs options | Required configuration is returned under `conditional_capabilities` | Set comparison values; execution determines actual result capabilities |

In the checked development environment, the executable example listed 6 current Methods (five defaults plus the authored example),
returned 6 available candidates without a goal, and one for explicit `metric_lookup`.
This measures structural narrowing, not model accuracy. Package availability can change
these counts. Tests supply resolved goals; no live LLM or live Databricks evaluation was
performed for this change. The grouping fixture checks query structure and result values,
not real warehouse joins or causal truth.

## Compatibility and next steps

Existing Method IDs, versions, Recipe pins, result capabilities and historical Run
snapshots are not rewritten. Explicit old interpretation labels retain their behavior.
The new interpretation default applies only to newly authored functions that omit it.
Malformed new function declarations now fail early; fix the declaration rather than
migrating stored evidence. The new discovery endpoint is additive.

Tests cover Python/REST report parity, MCP profile forwarding, Web requirement checks,
private inputs, valid execution and recorded query attempts. Existing access, scope,
budget, Recipe and provenance suites remain applicable because execution is shared.

**Not implemented:** semantic text verification, an automatic natural-language Method
selector, a learned ranker, or claims of model-independent selection. A future evaluation
should run fixed normal, ambiguous and unsupported questions through each target AI
client, recording selected Methods, clarification behavior and unsupported claims.
Only that evidence can support claims of improved end-to-end selection accuracy.
