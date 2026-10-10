# Architecture

Use this page when changing providers, execution or interfaces. For a first Method,
start with [the tutorial](guides/methods.md).

Decision Layer turns governed semantic references, reviewed analytical Methods and
reusable Recipes into recorded analyses. Web, REST, Python and MCP use the same
contracts and execution rules. [Product context](https://github.com/haechangcho/decision-layer/blob/main/docs/PRODUCT_CONTEXT.md) describes the
purpose; [Decisions](https://github.com/haechangcho/decision-layer/blob/main/docs/DECISIONS.md) records the detailed policies and their history.

## Code map

| Responsibility | Location |
| --- | --- |
| Canonical types and IDs | `src/decision_layer/core/` |
| Method implementation and authoring API | `src/decision_layer/methods/` |
| Local Method development | `src/decision_layer/dev.py` |
| Strict query fixtures | `src/decision_layer/testing.py` |
| Semantic contracts and Cube/dbt adapters | `src/decision_layer/semantic/` |
| Connection configuration and credential storage | `src/decision_layer/sources/` |
| Recipe validation, editing and promotion | `src/decision_layer/recipes/` |
| Run execution, jobs, evidence and storage | `src/decision_layer/runs/` |
| HTTP assembly and resource routes | `src/decision_layer/api/` |
| MCP client adapter | `src/decision_layer/mcp/` |
| Web routes | `web/app/` |
| Recipe and Run UI | `web/features/recipes/`, `web/features/runs/` |
| Shared Web controls and results | `web/components/` |
| Shared test providers and factories | `tests/support/` |
| Executable contributor examples | `examples/methods/` |

## Execution path

```text
Web / REST / Python / MCP
        ↓
Canonical invocation or Recipe
        ↓
RunEngine: scope, access, selection, policy and evidence
        ↓
MethodRegistry: input defaults, binding checks and result contract
        ↓
Method.run(ExecutionContext, bindings, params)
        ↓
ExecutionContext.dataset(DatasetSpec)
        ↓
Semantic provider → bounded Dataset
        ↓
MethodOutput → validation → Result → Run evidence
```

Local `MethodSession.run()` invokes the ordinary Registry and context in the caller's
Python event loop for breakpoints. It is a development trial with fresh budgets,
not a stored Run. `preview()` uses the RunEngine and memory storage. Neither uploads
code or evidence to a remote server. See ADR-079/080 and the [Method guide](guides/methods.md).

## Method and Recipe boundaries

A Method is one reusable analytical capability. Several queries and local combination
can belong to one Method. Current built-ins are aggregate, trend, drilldown,
peer comparison and CEM. Implementations are directly under `methods/`; logical IDs
retain `query.*` / `causal.*` for compatibility. Folder names do not establish causal claims.

`methods/__init__.py` exports authoring types and explicitly registers built-ins.
Implementation modules have no self-registration statements. The Registry applies
parameter/binding checks, records interpretation/provenance and rejects undeclared
artifact types, selections and capabilities. Analytical payload correctness needs
independent Method tests; `Artifact.data` is not a complete payload schema.

A Recipe encodes an organization's procedure using existing Methods and semantic
references. It does not define metric SQL or override source access/validation.
Typed source rules connect runtime inputs and earlier selections. Pipeline mode
executes fixed steps; investigation mode appends bounded approved Method choices.
See ADR-003/019/060/062/067/069/070.

## Semantic providers

Product connections are Cube REST and the official hosted dbt Semantic Layer GraphQL
API. No custom MetricFlow gateway is shipped. Each adapter maps native metadata into
SemanticCatalog and executes DatasetSpecs. A declared relationship is discovery
information, not proof of join/grain support. Actual execution still validates.

Metrics, dimensions, entities, joins, aggregation, grain and permissions belong to the
provider. Counts and ratio parts must be declared or verified by the adapter; Methods
must not infer them from nearby names or invent annotations. Missing metadata can
limit statistical analysis. See ADR-057/058/065/073/074 and the provider guides.

## Scope, validation and evidence

Execution policy owns period, deadline, query and returned-row bounds. Unresolved
periods require input; all-period execution requires explicit policy permission.
Current periods stay within Run scope, while comparisons may precede it under policy.
Observed date coverage is distinct from ingestion completeness (ADR-064/072).

Each logical provider execution records DatasetSpec before execution, including
failures and interruptions. Attempts consume budgets. Available provider query IDs,
SQL, freshness, warnings, Method versions and resolved input sources remain inspectable.
A successful query alone does not imply a valid analytical answer. Failed validators
refuse supported capabilities. Statistical uncertainty and causal interpretation
require their specific assumptions; CEM does not itself identify a causal effect.

MCP execution is question-scoped: typed goals, purposeful steps and evidence-linked
conclusions are required. Arbitrary generated analytical Python/SQL is not an execution
path. Source rules and result capabilities support selection without inferring intent
from narrative. See ADR-059/069/070/071.

## Access and persistence

Provider credentials are caller-scoped. Runs belong to their authenticated caller;
shared Runs are read-only and still require semantic visibility. Sources separately
manage connection configuration. Authentication and configuration rules are shared
HTTP dependencies, not logic copied into each UI.

Runs store Recipe/Method snapshots, invocation settings, attempts, outcomes and
provenance. Historical evidence is not rewritten when code or Recipes change.
Recipes are versioned YAML; Run stores support local memory, SQLite and PostgreSQL.
Background jobs use an in-process worker pool. This is not a distributed scheduler;
recovery marks interrupted work. See ADR-024/029/030/070.

## HTTP and Web ownership

`api/app.py` wires providers, storage, jobs, middleware and route groups. Resource
modules (`sources`, `semantic`, `methods`, `recipes`, `runs`) delegate to shared
services and the engine. Recipe semantic checks live in recipe authoring, reused by
validation and Run promotion.

Web creates canonical specs. Method metadata generates common input controls;
artifact renderers display supported results. Recipe/Run UI code lives with its
feature. A new Method using existing types should not need Method-name branches
in frontend, REST or MCP code.

## Missing definitions and extension

Runs can record blocked goals, missing semantic requirements and review-only provider
YAML drafts. The Web shows suggestions and evidence; users edit their source model
externally and ask again. Existing reviewed retry APIs remain compatible. No provider
model is edited or executed from a draft (ADR-075–078).

Extend a Method with reviewed Python and independent tests, a Recipe with canonical
specs, or a provider through its existing contract. Heavy libraries require explicit
dependencies and runtime version evidence. Notebook hosting, code-upload execution,
plugin installers, custom frontend runtimes and workflow schedulers remain deferred.
