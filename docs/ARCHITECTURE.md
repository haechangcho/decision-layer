# Decision Layer — Architecture

## 1. Architectural objective

Build a small, composable core that supports:

- one or more semantic providers,
- a registry of atomic analytical Methods,
- reusable Recipes,
- deterministic and constrained agentic execution,
- typed validation,
- typed results,
- provenance,
- Web/Python/API/MCP parity.

The architecture should make different extension axes independent:

```text
Semantic Provider:
  Cube -> MetricFlow -> ...

Method:
  Drilldown -> CEM -> DiD -> Forecast -> ...

Recipe:
  Revenue Investigation -> Retention Investigation -> ...

Interface:
  Web -> Python -> REST -> MCP
```

Adding one should not require modifying the others.

Product connections are Cube REST and the official dbt Semantic Layer GraphQL API.
The bundled dbt example also includes a local MetricFlow gateway (PostgreSQL).
Sources selects one active provider and preserves each provider's connection settings.
Canonical catalog objects declare `dimension_refs`, `time_dimension` and `count_measure`;
Methods consume those declarations instead of inferring relationships from a provider's reference path.
Connections do not require Decision Layer-specific model annotations. Adapters use native semantic
declarations; unknown sample counts and ratio components remain unknown rather than being guessed
from sibling metrics or custom `meta`. See ADR-057 for statistical capability limits.
The MetricFlow gateway runs in a separate dependency environment and translates typed dataset specs
into real MetricFlow engine requests. It does not expose raw SQL execution. See ADR-056 and
the [MetricFlow connection guide](guides/metricflow.md) for capabilities and authentication boundaries.
The hosted dbt adapter needs only a GraphQL endpoint, environment ID and caller token. It discovers
native metadata, submits `createQuery`, polls status and reads all bounded result pages. Provider query
IDs and available SQL remain in Run evidence. No local project or warehouse credentials are required;
see ADR-058 and the [dbt connection guide](guides/dbt.md).

MCP Method execution requires a question-scoped Run: start analysis (or a Recipe),
append Methods with a purpose, then save a conclusion linked to recorded steps.
The engine rejects MCP standalone Method calls and incomplete completion requests.
MCP pipelines remain open after execution until their conclusion is recorded. Web
shows this state as conclusion waiting and supports owner review and completion.
See ADR-059; no narrative or grouping is inferred from chat text.

Direct Run registration creates runtime-selection Recipes without a review dialog.
Recorded sources are preserved; unprotected literal targets use matching earlier
semantic dimension paths or required typed runtime inputs without remembered defaults.
This is a new-procedure policy, not recovery of historical intent (ADR-061).

Method authoring metadata generates shared input controls and canonical step defaults.
`configure_step` / `POST /recipes:configure-step` materializes explicit source rules,
not provider semantics or arbitrary agent code. Missing required targets become typed
runtime inputs without remembered values. See ADR-062 and the Method contribution guide.

Execution scope distinguishes unresolved, explicit all-period, date-range and relative-period
requests. Server-owned policy is checked before analysis and freshness queries and again at
the dataset boundary. Waiting Runs keep pending intent and resume through a revision-checked
owner scope update; no placeholder result is promoted to a Recipe. Relative rules resolve
against the execution clock, with provenance and policy revision stored on the Run. See ADR-064.

CEM supports native average outcomes through an explicit row count and a provider-declared queryable
primary unit, verifying one finite outcome and one counted row per unique unit. Continuous-outcome
significance is not implemented. The local MetricFlow adapter preserves aggregation types from the
native dbt artifact before planner normalization; hosted dbt metadata that cannot establish this
contract still fails closed. Sample campaign modeling stays outside the generic engine. See ADR-065.

---

## 2. High-level architecture

```text
                         User / AI Agent
                               │
                    ┌──────────┴──────────┐
                    │                     │
                   Web               Python / MCP
                    │                     │
                    └──────────┬──────────┘
                               ▼
                         Analysis API
                               │
                    Intent / Recipe Router
                               │
                               ▼
                         Analysis Planner
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
      Recipe Registry     Method Registry      Validators
           │                   │                   │
           └───────────────────┼───────────────────┘
                               ▼
                         Dataset Planner
                               │
                               ▼
                     Semantic Provider API
                               │
                      ┌────────┴────────┐
                      │                 │
                    Cube            Future
                      │
                      ▼
                  Warehouse
                      │
                      ▼
                 Dataset / Rows
                      │
                      ▼
                  Method Runtime
                      │
                      ▼
                   Validation
                      │
                      ▼
                   Typed Result
                      │
                   Provenance
```

---

## 3. Core packages

Suggested initial structure:

```text
decision_layer/
├── core/
│   ├── ids.py
│   ├── models.py
│   ├── result.py
│   ├── errors.py
│   └── capabilities.py
│
├── semantic/
│   ├── provider.py
│   ├── catalog.py
│   ├── dataset_spec.py
│   └── providers/
│       ├── cube/
│       └── sql/            # optional/reference provider
│
├── methods/
│   ├── registry.py
│   ├── base.py
│   ├── query/
│   │   ├── compare/
│   │   ├── drilldown/
│   │   ├── contribution/
│   │   └── related_metrics/
│   ├── stats/
│   │   └── ols/
│   └── causal/
│       ├── cem/
│       └── did_simple/
│
├── recipes/
│   ├── schema.py
│   ├── registry.py
│   ├── planner.py
│   └── runtime.py
│
├── validation/
│   ├── base.py
│   ├── registry.py
│   └── builtin/
│
├── agent/
│   ├── router.py
│   ├── resolver.py
│   ├── investigator.py
│   └── narrator.py
│
├── evals/
│   ├── schema.py
│   └── runner.py
│
├── api/
│   └── ...
│
├── mcp/
│   └── ...
│
└── sdk/
    └── ...
```

The exact module names may change; preserve responsibility boundaries.

---

## 4. Stable identifiers

Use stable logical identifiers from the start.

Examples:

```text
semantic://cube-prod/sales/revenue
method://query/drilldown@1.0.0
recipe://revenue-investigation@2.1.0
run://01J...
result://01J...
```

Provider-specific references may retain an external form:

```text
cube://production/sales/revenue
```

The internal model should preserve:
- provider,
- instance,
- external object ID,
- version/hash if available.

This enables future Decision Graph integration without coupling the graph to internal database IDs.

---

## 5. Semantic Provider contract

A semantic provider owns access to governed data semantics.

Conceptual interface:

```python
class SemanticProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities:
        ...

    def discover(self) -> SemanticCatalog:
        ...

    def resolve(self, refs: list[SemanticRef]) -> list[SemanticObject]:
        ...

    def validate_dataset(self, spec: DatasetSpec) -> ValidationResult:
        ...

    def compile(self, spec: DatasetSpec) -> CompiledQuery:
        ...

    def execute(self, query: CompiledQuery) -> Dataset:
        ...
```

### Provider capabilities

Do not assume all semantic systems support the same features.

Example:

```json
{
  "aggregate_queries": true,
  "entity_grain_queries": true,
  "time_dimensions": true,
  "join_discovery": true,
  "custom_metadata": true,
  "compiled_sql": true
}
```

Methods declare required capabilities.

If a provider cannot satisfy them, fail before execution.

---

## 6. Canonical Semantic Catalog

Provider-specific metadata must be translated into a canonical internal representation.

Conceptual entities:

```text
SemanticObject
├── id
├── name
├── kind
│   ├── metric
│   ├── measure
│   ├── dimension
│   ├── entity
│   └── time_dimension
├── data_type
├── grain
├── description
├── owner
├── freshness metadata
├── external_ref
└── provider metadata
```

Do not flatten away provider-specific metadata; keep a generic metadata map when necessary.

---

## 7. Method contract

A Method is an atomic analytical capability.

Conceptual manifest:

```yaml
api_version: decision-layer/v1

name: causal.cem
version: 1.0.0
kind: causal

roles:
  unit:
    semantic_type: entity
    required: true

  treatment:
    data_type: boolean
    required: true

  outcome:
    data_type: numeric
    required: true

  covariates:
    multiple: true
    required: true

parameters:
  estimand:
    type: enum
    values: [ATT]
    default: ATT

dataset:
  grain: entity
  requires_row_level: true

execution:
  mode: dataframe

diagnostics:
  - balance
  - sample_retention

outputs:
  - estimate
  - confidence_interval
  - balance
  - sample_summary
```

### Method responsibilities

A Method may define:
- schema,
- validation,
- dataset requirements,
- executor,
- diagnostics,
- output schema.

A Method must not:
- redefine semantic metric logic,
- know organization-specific “Revenue should be broken down by Product” rules,
- contain UI-specific code.

---

## 8. Execution modes

Methods should declare how they execute.

### semantic_pushdown

Best for:
- drilldown,
- ranking,
- comparison,
- contribution where possible.

The provider/warehouse does most computation.

### dataframe

Best for:
- OLS,
- CEM,
- statistical tests.

The Dataset Planner materializes only required columns and rows.

### hybrid

Best for:
- methods requiring warehouse aggregation followed by local statistical computation.

This separation is important for scalability.

---

## 9. DatasetSpec and Dataset Planner

Dataset planning is a core differentiator.

The same semantic metric may need different physical shapes depending on Method.

### Drilldown

```yaml
grain: aggregate
metric: sales.revenue
dimensions:
  - sales.product
```

### CEM

```yaml
grain:
  entity: customer.id

fields:
  - customer.promotion_received
  - customer.age
  - customer.tenure
  - sales.revenue_30d_before
  - sales.revenue_30d_after
```

### DiD

```yaml
grain:
  - store.id
  - week

fields:
  - store.ai_enabled
  - sales.weekly_revenue
```

The Dataset Planner:
1. reads Method dataset requirements,
2. reads bound semantic roles,
3. verifies provider capability,
4. generates DatasetSpec,
5. asks provider to compile/execute it.

Do not let each Method directly talk to Cube.

---

## 10. Recipe contract

A Recipe is a reusable analysis SOP.

Conceptual schema:

```yaml
kind: AnalysisRecipe

metadata:
  name: revenue_investigation
  version: 1.0.0
  description: Investigate changes in revenue.

routing:
  use_for:
    - revenue_drop
    - revenue_growth
    - metric_change
  do_not_use_for:
    - causal_effect

semantic_scope:
  primary_metric: cube://production/sales/revenue

  related_metrics:
    - cube://production/sales/quantity
    - cube://production/sales/avg_unit_price
    - cube://production/sales/discount_rate

  preferred_dimensions:
    - cube://production/sales/product
    - cube://production/sales/region
    - cube://production/customer/segment

execution:
  mode: investigation

  allowed_methods:
    - query.compare
    - query.contribution
    - query.drilldown
    - query.related_metrics

  limits:
    max_steps: 12
    max_queries: 20

validators:
  - complete_period
  - freshness

instructions: |
  Do not make causal claims.
  If wholesale dominates the change, report it separately.

output:
  sections:
    - headline
    - largest_contributors
    - supporting_metrics
    - caveats
```

### Typed core + bounded free text

Recipe semantics should primarily live in typed fields.

Free-form `instructions` are allowed for:
- caveats,
- domain gotchas,
- reporting preferences.

Free text must not be allowed to:
- redefine a semantic metric,
- override security/access,
- bypass validators,
- enable arbitrary code execution.

---

## 11. Recipe execution modes

### pipeline

For fixed procedures.

Example:
```text
CEM -> Balance -> Weighted OLS -> Result
```

### investigation

For iterative analytics.

Pseudo-loop:

```text
plan next allowed step
  ↓
execute Method
  ↓
inspect typed Result
  ↓
run validators
  ↓
stop or select next allowed Method
```

The investigation runtime must enforce:
- allowed Method set,
- max steps,
- max queries,
- provider access restrictions,
- Recipe semantic scope,
- validation failures.

The LLM proposes steps; the runtime authorizes and executes them.

---

## 12. Analysis Plan

The Plan is the concrete execution intent for one request.

Example:

```json
{
  "recipe": "recipe://revenue-investigation@2.1.0",
  "question": "Why did revenue fall last month?",
  "resolved_entities": {
    "primary_metric": "cube://production/sales/revenue"
  },
  "steps": [
    {
      "method": "method://query/compare@1.0.0",
      "params": {"comparison": "previous_complete_period"}
    },
    {
      "method": "method://query/contribution@1.0.0",
      "foreach": ["product", "region", "customer_segment"]
    }
  ]
}
```

For investigation mode, later steps may be appended as results arrive.

---

## 13. Validation architecture

Validation should be composable.

Sources:
- provider,
- Method,
- Recipe,
- future namespace/policy scope.

Conceptual API:

```python
class Validator(Protocol):
    def validate(self, context) -> ValidationResult:
        ...
```

Validation result:

```json
{
  "status": "pass|warning|fail",
  "code": "DATA_STALE",
  "message": "...",
  "details": {}
}
```

### Initial validator categories

Data:
- freshness,
- non-empty,
- completeness,
- expected range.

Query:
- required filter,
- complete comparison period,
- valid time zone.

Statistical:
- minimum sample,
- variance,
- multicollinearity if applicable.

Causal:
- overlap,
- covariate balance,
- treatment timing compatibility,
- panel completeness.

Interpretation:
- prevent causal narration from associational Method outputs.

---

## 14. Typed Result protocol

Results should be renderer-neutral.

Conceptual structure:

```json
{
  "kind": "analysis_result",
  "status": "success",
  "primary": {
    "type": "estimate",
    "value": 12430,
    "unit": "KRW"
  },
  "artifacts": [
    {
      "type": "breakdown_table",
      "data": []
    },
    {
      "type": "balance",
      "data": []
    }
  ],
  "warnings": [],
  "validation": [],
  "provenance": {}
}
```

Initial result artifact types:

```text
estimate
confidence_interval
table
breakdown_table
contribution_table
coefficient_table
balance
sample_summary
time_series
warning
```

Web and MCP consume the same protocol.

---

## 15. Provenance

Every Run should record enough information to reproduce or review the answer.

Minimum:

```text
question/invocation
resolved semantic refs
semantic provider + instance
semantic model/version/hash if available
recipe + version
methods + versions
analysis plan
dataset specs
compiled query/spec
freshness
validators + outcomes
runtime/library versions
timestamps
result
```

The UI should eventually expose:

```text
How was this calculated?
```

and show these details.

---

## 16. Natural-language runtime

Suggested separation:

### Resolver
Maps user concepts to existing semantic objects.

Must never fabricate a semantic field.

### Router
Selects:
- direct Method,
- or Recipe.

### Planner
Instantiates a typed Analysis Plan.

### Investigator
For `execution.mode=investigation`, selects the next action from an allowlist.

### Narrator
Explains typed results.

The Narrator must honor result semantics:
- descriptive,
- associational,
- causal,
- diagnostic.

---

## 17. API surface

Possible REST concepts:

```text
GET  /sources
POST /sources

GET  /semantic/catalog

GET  /methods
GET  /methods/{name}

GET  /recipes
POST /recipes
GET  /recipes/{id}

POST /plans
POST /runs

GET  /runs/{id}
GET  /results/{id}

POST /evals/run
```

Avoid API routes tied to the Web UI.

---

## 18. MCP surface

MCP should be a thin interface over the canonical API.

Possible tools:

```text
list_sources
get_semantic_catalog

list_methods
describe_method

list_recipes
describe_recipe

plan_analysis
validate_analysis
run_analysis

get_run
get_result
```

Do not create one MCP tool per Method.

---

## 19. Web architecture

The Web app should be schema-driven.

The root `compose.yaml` runs the API and Web as separate containers for local
onboarding against an existing Cube. The Web proxies `/api/*` to the API;
SQLite and Recipe YAML persist in separate named volumes. Default published
ports bind to localhost. The sample-data stack remains under `examples/`.
Recipe writes currently require a provider-accepted caller but no author role
(ADR-038). Keep the API private until Authentik-backed application authorization
is implemented; Cube identity and data permissions do not grant editing rights.
Each executed Run step stores the effective Method parameters and per-parameter
source (Method default, Recipe, or runtime request), following ADR-039.

### Core pages

```text
Sources
Recipes
Methods
Runs
Evals
```

### Method UI

Generate from Method schema:
- semantic field picker,
- metric picker,
- dimension picker,
- entity picker,
- enum,
- number,
- boolean,
- date/time,
- bins.

Avoid:
```text
CEMPage.tsx
DIDPage.tsx
OLSPage.tsx
```

### Recipe UI

Provide a Recipe builder using:
- target semantic refs,
- allowed Methods,
- related metrics,
- preferred dimensions,
- validators,
- execution mode,
- limits,
- optional bounded instructions.

Do not build a generic Airflow-style DAG editor in MVP.

### Custom frontend plugins

Do not support arbitrary Method-supplied React components in MVP.

This creates:
- security,
- versioning,
- build,
- design-system,
- sandboxing problems.

Use generic primitives first.

---

## 20. Repository/plugin extension

Future Method plugins can use Python entry points.

Conceptual:

```toml
[project.entry-points."decision_layer.methods"]
synthetic_control = "decision_layer_synth:method"
```

Installing a Method should automatically make it available through:
- API,
- MCP,
- generic Web UI,
- Recipe builder,

as long as its schema uses supported primitives.

---

## 21. Git-first configuration

Recipes, validators, evals, and reference context should eventually be representable as files.

Suggested:

```text
analytics/
├── recipes/
│   ├── revenue-investigation.yaml
│   └── retention-investigation.yaml
├── references/
│   └── growth.md
├── validators/
└── evals/
```

The Web UI may store or edit these objects, but import/export and versionability should remain possible.

Avoid making critical institutional knowledge only exist in an opaque application database.

---

## 22. Decision Graph compatibility

Do not implement a Decision Graph in MVP.

Preserve compatibility by:
- stable object IDs,
- explicit semantic refs,
- Run/Result IDs,
- externally queryable metadata.

Future graph edges might be:

```text
Metric -> recommended_recipe -> Recipe
Hypothesis -> evaluated_by -> Analysis/Run
Run -> supports/refutes -> Hypothesis
Decision -> supported_by -> Result
```

This future layer should reference Decision Layer, not become a prerequisite for it.

## Reusable Step Inputs (ADR-060)

Step parameters accept literals, declared Recipe runtime inputs, and bounded references to manifest-declared selection outputs of earlier steps. `ranked_groups` carries eligible full-precision paths, scores, ordering and population completeness independently of displayed rows. The resolver supports only first-ranked selection and full-path/current-condition/parent-condition projections. It refuses incomplete or unavailable results and requests input on ties; it never runs generated code or uses previous Run values.

`StepRecord.requested_step` retains the rule; `StepRecord.step` retains actual applied inputs including Method defaults. `input_resolutions` explains the dependency, projection, selected value and ranking evidence. Recipe inputs are validated before Run creation and preserved in scope. Result semantic refs and queries continue to pass through the same current-credential provider contract.

Run-to-Recipe review preserves these rules rather than copying resolved winners. Historical exploratory literals require explicit review, with no guessed dependencies. Run-specific dates and extra shared filters are not permanent Recipe rules. Existing immutable Recipe snapshots can recover previously authored references. A selected subset must include its earlier dependencies. User-directed changes create a newer Recipe version, leaving historical Runs unchanged.
