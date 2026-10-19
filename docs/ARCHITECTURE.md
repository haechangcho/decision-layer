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
| Ordinary function registration, query inputs and worker checks | `src/decision_layer/methods/function/` |
| Built-in catalog assembly | `src/decision_layer/methods/catalog.py` |
| Local Method development | `src/decision_layer/dev.py` |
| Project discovery, file scaffolding and CLI | `src/decision_layer/project.py`, `src/decision_layer/project_scaffold.py`, `src/decision_layer/cli.py` |
| Strict query fixtures | `src/decision_layer/testing.py` |
| Semantic contracts and Cube adapter (legacy dbt retained) | `src/decision_layer/semantic/` |
| Connection configuration and credential storage | `src/decision_layer/sources/` |
| Recipe validation, editing and promotion | `src/decision_layer/recipes/` |
| Run execution, jobs, evidence and storage | `src/decision_layer/runs/` |
| HTTP assembly and resource routes | `src/decision_layer/api/` |
| Host/origin policy and operator permissions | `src/decision_layer/api/http.py`, `src/decision_layer/api/permissions.py` |
| MCP tools, evidence views and instruction text | `src/decision_layer/mcp/server.py`, `presentation.py`, `instructions.py` |
| Web routes | `web/app/` |
| Method, Recipe and Run UI | `web/features/methods/`, `web/features/recipes/`, `web/features/runs/` |
| Shared Web controls and results | `web/components/` |
| Shared test providers and factories | `tests/support/` |
| Learning notebooks | `docs/tutorials/` |
| Importable Method and Recipe examples | `examples/methods/`, `examples/recipes/` |
| Example and notebook verification | `tests/examples/` |

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
ctx.aggregate/entities → ExecutionContext.dataset(DatasetSpec)
        ↓
Semantic provider → bounded Dataset
        ↓
MethodOutput → validation → Result → Run evidence
```

Local `MethodSession.run()` invokes the ordinary Registry and context in the caller's
Python event loop for breakpoints. It is a development trial with fresh budgets,
not a stored Run. `preview()` uses the RunEngine and memory storage. Neither uploads
code or evidence to a remote server. See ADR-079/080 and the [Method guide](guides/methods.md).

`@method` turns a typed Python signature into the existing manifest/Method adapter. Input maps normalize into canonical bindings. `ctx.aggregate/entities` build governed DatasetSpecs; `ctx.compute` uses in-process local debugging or bounded server child computation. Optional dependencies are checked before queries. No new provider planner or notebook product is introduced. ADR-100 adds an opt-in trusted local code publication path. See ADR-081 and the [manual scenarios](guides/method-scenarios.md).

External-library APIs remain visible in authored calculation functions. `ctx.compute`
is an execution boundary, not an estimator facade. Analysis-specific assumptions
and fit conditions remain explicit; shared execution owns semantic access, extraction
bounds and evidence. Existing builtin helper reuse does not define the extension API.

## Method and Recipe boundaries

A Method is one reusable analytical capability. Several queries and local combination
can belong to one Method. The default catalog contains Korean lookup/trend/drilldown/peer Skills and
DoWhy binary
matching and numeric-treatment OLS regression adjustment. Optional implementations
include unit analyses, OLS, regression adjustment, DML and panel
contrasts; Python aggregate/trend/drilldown/peer, CEM and prior statistical contracts remain compatibility-only. Implementations are directly under `methods/`; logical IDs
retain `query.*` / `causal.*` for compatibility. Folder names do not establish causal claims.

`methods/__init__.py` exports authoring types and the default registry.
`methods/catalog.py` explicitly assembles built-ins and retained versions.
Team definitions use a marked `decision-layer.yaml` project. Its importable
`<name>/methods/` package contains `method.py` (one METHOD export) or `SKILL.md`
entries. CLI check/list, MethodSession.load_project and API startup use project.py
and the existing Registry. Lists report the definition path; DL_PROJECT_DIR selects
one project in deployment. Legacy module/Skill-directory settings remain supported.
See ADR-106 and the [project guide](guides/method-projects.md).
Implementation modules have no self-registration statements. The Registry applies
parameter/binding checks, records interpretation/provenance and rejects undeclared
artifact types, selections and capabilities. Analytical payload correctness needs
independent Method tests; `Artifact.data` is not a complete payload schema.

New function Methods return `Table` for grouped and time-bucketed queries, or
`Estimate` for a scalar estimate. `Table.from_dataset` keeps row data and governed
column metadata (alias, reference, role, granularity) on the canonical Artifact.
Shared Web presentation uses explicit column roles for ungrouped time trends;
ordinary dated rows are not automatically interpreted as trends. Existing
`TimeSeries` implementations, builtin trend versions and stored Runs remain readable.
See ADR-085.

The public Column/DataInput authoring models compile to the existing core
DataInput/RoleSpec contract at registration (ADR-108). Explicit sources govern
selection; matching column arguments are inferred once, with ambiguous ownership
rejected. A Column with role="entity_key" compiles to a canonical entity role
and uses the same named bindings as other columns (ADR-109). Its DataFrame alias
preserves the declared name. Legacy entity inputs remain supported. Web/REST/MCP
continue to consume the same canonical manifest and execute the same Registry.

New observational Methods use `association` for summaries and relationships.
Legacy `descriptive`/`associational` manifests and stored results retain their labels
and contracts. Routing and completion accept either legacy noncausal label for new
association goals while still checking required capabilities and semantic scope.
Existing goal rules and conditional causal interpretation remain unchanged (ADR-086).

A Recipe encodes an organization's procedure using existing Methods and semantic
references. It does not define metric SQL or override source access/validation.
Typed source rules connect runtime inputs and earlier selections. Pipeline mode
executes fixed steps; investigation mode appends bounded approved Method choices.
See ADR-003/019/060/062/067/069/070.

## Semantic providers

The initial product connection is Cube REST only (ADR-096). Source configuration,
provider factory and Web do not offer dbt or direct warehouse connectors. The legacy
dbt module and its isolated regression tests remain for reference; generic provider
contracts remain available for tests and future work. No custom MetricFlow gateway
is shipped. The Cube adapter maps native metadata into
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

Python callers use named function arguments; normalization and role/parameter categorization remain internal. New statistical Methods have bounded, specific contracts without AnalysisDesign or assumption checkboxes. They report unverified assumptions and associational estimates. Legacy IDs/versions retain their original contracts in a compatibility module (ADR-084).

Read-only Method discovery (`methods/discovery.py`) serves local Python, REST, MCP and
Web requirement checks. It reuses AnalysisGoal and Registry role validation, returns
candidate contracts and exclusion reasons, and never infers analytical intent or runs
queries. Function Methods default to association and use a docstring for purpose.
Optional result assertions remain distinct from search tags. MCP no longer imposes a
CEM or change-analysis procedure independently of Recipes. See ADR-087 and the paired
[discovery guide](guides/method-discovery.md).

The default Method catalog excludes the three retired design-object statistical
contracts. Registry lookup keeps them executable for explicitly referenced legacy
Recipes; discovery and Web/REST/MCP lists show current choices only. No historical
evidence or analytical implementations are deleted (ADR-088).

CEM is also compatibility-only: default discovery excludes causal.cem, while explicit
legacy Recipe lookup retains its original implementation (ADR-089).

Current Skills cover lookup, trends and branch investigation; executable time calculations/checks are separate.
Optional reviewed implementations become discoverable through ordinary registry.register;
there is no separate plugin runtime, UI installer or automatic dependency installation.
Explicit existing Recipe references still resolve compatibility registrations (ADR-090).

DoWhy matching uses a distinct native estimator and ATT contrast; regression adjustment
retains the existing ATE contrast. Observed diagnostics and assumed backdoor graphs do
not promote either to an established causal effect. See ADR-091 and the
[statistical guide](guides/statistical-methods.md).

Numeric regression defaults to a constant change per stored treatment unit; explicit
contrasts are optional. The old binary regression contract remains compatible while
new discovery uses stats.regression_adjustment. See ADR-092.

## PRD implementation increment (2026-10-15)

Native synchronous calculations can use `methods.calculation` and `InputTable`;
these compile to the same Method/Registry/context path, preserving scoped source
queries and result evidence. Existing typed async Methods remain the advanced
route. See ADR-095 and the updated paired workshop notebooks.

Source HTTP administration now requires a configured key and an operator-approved
endpoint. Recipe editors/publishers are distinct permissions; Run promotion is
owner-only and saves a draft. Retirement markers preserve YAML versions, with
publisher restore and filesystem audit events. Local/demo modes only are supported;
shared mode fails closed pending independent application identity, egress controls
and code isolation. See ADR-094 for migration and exact limits. SQL-source adapters,
SELECT AST policy and multi-source input profiles remain PRD proposals.

## Method asset entry points (ADR-097)

`methods/python.py` adapts ordinary functions to MethodRegistry → ExecutionContext
→ existing bounded compute worker. `DataInput` maps named function inputs to scoped
Cube extraction; execution and provenance are not implemented separately per UI.
`methods/skills.py` parses Markdown assets. Skill manifests use
`implementation=skill`, `execution=agent_guided`. Advisory-only assets remain
Run-level guidance. ADR-098 adds `query_execution: true` assets with
`agent_executable=true`, accepted as Recipe/Run stages. `runs/skills.py` validates
structured Cube queries through the same ExecutionContext, persists each request
before execution and records actual results/errors. The pipeline pauses for an
external client agent and resumes after evidence-backed finish. It does not execute
Markdown as code or certify prose adherence. Legacy manifests default to Python.

`StepRecord.skill` snapshots the manifest/text/version/hash and query log.
`Run.active_skill_step` survives storage/restart; interrupted reads are marked and
not silently retried. Query IDs are idempotent only for identical requests. Shared
viewers cannot mutate stages. Selections reference returned query rows and export
full filters; `DataInput.filters_parameter` passes this population to later Python.
Skill completion currently grants no analytical capability. Runtime execution and
advisory Run.method_guides are distinct evidence records.

`methods/loading.py` clones the built-in registry per application, imports reviewed
`DL_METHOD_MODULES` exports and loads `DL_SKILLS_DIR`. Recipe stores, routing,
configuration, promotion and the engine share this registry. Opt-in operator asset routes manage versioned drafts and reviewed publication
(ADR-100). Module import is trusted code execution, not a sandbox.

GET `/methods/{name}/guide` returns a Skill; GET `/method-guides/authoring` and
`/method-guides/cube-query` return bundled guidance. MCP exposes these progressively
through describe_method/get_method_guide; start_analysis accepts `guide`. Web shows
Skill guidance separately from executable configuration and historical Run checks.

MCP evidence is bounded separately from storage (ADR-098 follow-up). Run responses
retain active Skill guidance and query summaries; `run_skill_query` returns the first
25 rows, and `get_skill_query` pages recorded rows with absolute selection indices.
The latter uses the authorized Run read route and never re-queries Cube. Full native
queries, errors and original rows remain in Run storage and the Web evidence view.

## Method source and operator editor (ADR-100)

`methods/source.py` captures the registered Python entry module and selected local
helpers with hashes. New `StepRecord.code` snapshots these sources and the selected
version; historical Runs without code remain explicitly unavailable. This is not an
archive of all dependencies, dynamic imports or external-library internals.

`methods/assets.py` owns drafts (optimistic revision/base-version checks), immutable
modules and published metadata in DL_METHOD_ASSETS_DIR. UI edits never modify installed
Git/package files. Operator-owned Git modules remain the original source for installed
versions; managed UI releases own their new version files. Export/copy reviewed changes
to Git explicitly; there is no silent bidirectional synchronization. Skill checks parse
frontmatter/contracts; Python checks execute imports in a credential-reduced child with
a 15-second limit. Publication imports reviewed trusted code into the server. Neither
check proves analytical quality or provides an untrusted-code sandbox.

Editing requires DL_ALLOW_METHOD_EDITING and separate DL_METHOD_EDITORS/PUBLISHERS
roles (or the explicit local service operator). Python import checks and publication
require a Method publisher. Recipe publication alone grants no code privilege. Shared
deployments remain blocked. The complete-journey local demo enables the editor; generic
Compose defaults to disabled. Host/Origin checks and canonical Run access still apply.

The registry retains installed and managed versions; pinned Recipes resolve the exact
registered version, and unknown pins are rejected at new authoring/execution.
Historical Recipe metadata with unavailable pins remains readable at startup; it
cannot execute through the current-version structural-validation fallback. Publishing
does not alter pending Skill snapshots or old Python records. Managed modules remain
importable after restart for computation workers. This storage supports the existing
single-process local API; cross-process publication coordination is not implemented.
An installed-package/UI version collision requires explicit source reconciliation;
startup refuses to silently replace a distinct source under the same version.

## Authoring surface versus execution evidence (ADR-101)

Source capture retains exact entry/helper modules and a separate selected-asset
module for reading/editing. The selected module includes required checks and
registration, excludes unrelated Recipes/Methods when statically resolvable, and
falls back for dynamic initialization. Full source remains evidence, not required
contributor boilerplate. The series-diagnostics 1.1.0 calculation now lives in
`methods/series_diagnostics.py`; `time_analysis.py` retains its source-specific
extraction/check/output adapter and pinned 1.0.0 implementation. New general
calculations still use ordinary functions with DataInput registration.

## Ordinary calculation input contracts (ADR-102)

ADR-105 adds `DataInput.column_args`: the existing adapter passes resolved column
names into ordinary functions such as `ols(data, outcome, treatment, confounders)`.
Roles still own semantic binding; scalar/list column arguments are not parameters.
The manifest drives REST/MCP/Web and records actual argument mappings with query
evidence. No new planner or execution endpoint is introduced. Web Method details
link to the existing unsaved single-step Recipe preview for data testing.

New calculations consistently register through `python_method` + `DataInput`.
DataInput is a canonical model, exposed in MethodManifest.data_inputs and re-exported
from methods. Its roles drive the same registry checks and scoped Cube extraction.
Entity inputs can declare mixed/list-valued variables with existing RoleSpec; all
resolved aliases/references and actual query evidence are recorded. Option checks
run in the bounded worker before querying; data checks run before calculation.
No credential/context object is passed to the ordinary function.

`native_matching.py` and `native_regression.py` implement the new 1.1.0 default
functions; their old modules/1.0.0 contracts remain frozen. `compatibility.py`
centralizes legacy/optional registration. Series and period-change adapters are
compatibility-only (ADR-103). `calculation/InputTable`
is retained for compatibility, not a second recommended authoring API.

## Default catalog retirement (ADR-103)

Period change, series diagnostics and the example household regression are now
compatibility-only. Current drilldown/trend Skills 1.1.0 do not refer to them.
Released instructions live in `guides/compatibility` for pinned lookup; the default
catalog loads current `guides/methods`. Operator modules can export historical
`COMPATIBILITY_METHODS`; managed version loading/publication preserves that status.
The current campaign example contains two query Skills, with no automatic Python tail.

## Shared Python authoring format (ADR-104)

`methods/formatting.py` runs the pinned Ruff formatter on bounded text with a fixed
bundled style, timeout and AST-equivalence check. It never imports supplied code.
The editing-only REST format endpoint calls it in a worker thread and returns text
without writes. Source capture applies it to the focused authoring projection,
retaining exact full files/hashes. Web code formatting is reversible and resets
review; line-based diffs use bounded jsdiff with context/line numbers. Stored Run
snapshots and immutable managed releases keep their original bytes.


## Packaged local admin console (ADR-107)

`decision_layer/console.py` mounts the same FastAPI instance at `/api` and the
existing root paths, and serves built React pages under `/ui`. CLI `serve` uses
this factory; `--api-only` uses the original FastAPI entry. `web/console` provides
only routing and project context; Method/Recipe/Run pages remain shared with Next.
`npm run build:console` creates package assets; release CI builds these before
wheel/sdist packaging. Users need only Python to start the installed local app.


## Internal execution boundaries (ADR-111)

`methods/python.py` retains PythonMethod and python_method as public entry points.
It coordinates three internal stages in `methods/function/`: `registration.py`
compiles the manifest and option adapters, `inputs.py` queries and records resolved
aliases, and `execution.py` validates materialized inputs and calls reviewed code.
Option and data checks share one implementation while retaining their distinct
validation codes. Worker arguments still contain no provider client or credentials.

`runs/engine.py` owns Run lifecycle, locks and background jobs. `runs/steps.py` owns
one step's expression resolution, Python/Skill dispatch and evidence record;
`runs/context.py` owns bounded query contexts and attempt persistence;
`runs/policy.py` owns limits and Recipe scope; `runs/access.py` owns private/shared
read checks. They receive explicit dependencies and do not import RunEngine. Stable
errors live in `runs/errors.py` and remain importable from the engine module.

MCP tool registration and HTTP calls remain in `mcp/server.py`; bounded evidence
projection lives in `mcp/presentation.py` and instruction text in `instructions.py`.
API middleware lives in `api/http.py`, permission rules in `api/permissions.py`,
with existing dependency imports retained. CLI scaffolding uses `project_scaffold.py`.

The Recipe editor composes `recipe-nodes.tsx`, `recipe-fields.tsx` and
`step-settings.tsx`. Pure defaults, selectors and error mapping live in
`editor-model.ts`. Saving, YAML reconciliation and preview state remain owned by
the editor, with no duplicate API or execution rules.
