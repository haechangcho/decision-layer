# Decision Layer — MVP Implementation Plan

## 1. MVP goal

Prove this single end-to-end thesis:

> A user can connect a Cube semantic model, define or use a reusable analytical Recipe/Method, ask a question or execute it directly, and receive a reproducible typed result with validation and provenance.

Do not attempt to prove every future product idea.

---

## 2. MVP success scenario

A user installs Decision Layer and connects Cube.

A senior analyst creates:

**Revenue Investigation**

- target metric: Revenue,
- preferred dimensions: Product, Region, Customer Segment,
- related metrics: Quantity, Average Unit Price, Discount Rate,
- previous-complete-period comparison,
- allowed Methods:
  - compare,
  - contribution,
  - drilldown,
  - related metrics.

A user asks:

> “Why did revenue fall last month?”

Decision Layer:
1. resolves Revenue to the Cube semantic object,
2. selects Revenue Investigation,
3. queries previous/current complete periods,
4. identifies the largest contributing product/segment,
5. inspects related metrics,
6. optionally performs one more drill-down,
7. runs freshness/completeness validation,
8. produces a typed result,
9. shows provenance.

A second scenario demonstrates one statistical/causal Method such as CEM or OLS.

---

## 3. MVP scope

### Semantic provider
- Cube only

### Methods

Query:
- `query.compare`
- `query.drilldown`
- `query.contribution`
- `query.related_metrics`

Statistics:
- `stats.ols`

Causal:
- choose **one** of:
  - `causal.cem`
  - `causal.did.simple`

Recommendation:
- implement CEM first if the goal is to stress-test entity-level Dataset Planning,
- implement simple DiD next if panel-shape support is important.

### Recipes
- Revenue Investigation
- one causal/statistical Recipe

### Validators
- freshness,
- complete comparison period,
- non-empty result,
- minimum sample,
- method-specific diagnostics for CEM/OLS.

### Interfaces
- REST API
- minimal Web UI
- Python SDK
- MCP server

### Result types
- estimate,
- table,
- breakdown table,
- contribution table,
- coefficient table,
- balance/sample summary if CEM,
- warning,
- provenance.

---

## 4. Explicitly out of scope

Do not implement in MVP:

- trigger/scheduler system,
- Decision Graph,
- KPI graph,
- full Domain/Domain Pack abstraction,
- arbitrary workflow DAG editor,
- notebook environment,
- Superset publishing,
- many semantic providers,
- unrestricted raw SQL agent,
- arbitrary frontend plugin components,
- automatic causal discovery,
- custom ML training,
- full enterprise RBAC beyond what is needed to respect Cube/provider access.

---

## 5. Phase 0 — Repository and contracts

### Deliverables

- package structure,
- Pydantic/domain models,
- stable IDs,
- Method interface,
- Recipe schema,
- SemanticProvider interface,
- DatasetSpec,
- Run/Result schemas,
- Validator interface.

### Acceptance criteria

Can instantiate and serialize:

```text
SemanticRef
MethodManifest
Recipe
AnalysisPlan
DatasetSpec
Run
Result
ValidationResult
```

No external database/provider required yet.

---

## 6. Phase 1 — Cube provider

### Deliverables

- connection configuration,
- connection test,
- semantic metadata discovery,
- canonical Semantic Catalog conversion,
- provider capabilities,
- aggregate DatasetSpec compilation/execution,
- entity-level DatasetSpec support if required by selected Method.

### UX target

```text
Connect Cube
  ↓
Connection successful
  ↓
Models/measures/dimensions/entities discovered
```

### Acceptance criteria

Given known semantic refs, Decision Layer can:
- resolve them,
- validate them,
- query them at requested grain,
- return a dataset plus provider provenance.

---

## 7. Phase 2 — Query Methods

Implement:

### `query.compare`

Input:
- metric,
- current period,
- comparison period.

Output:
- current,
- previous,
- absolute change,
- relative change.

### `query.drilldown`

Input:
- metric,
- dimension,
- period/filter context.

Output:
- typed breakdown table.

### `query.contribution`

Input:
- metric,
- dimension,
- comparison periods.

Output:
- contribution by member/category.

### `query.related_metrics`

Input:
- list of semantic metrics,
- inherited filters/scope.

Output:
- typed metric comparison table.

### Acceptance criteria

All Methods:
- register automatically,
- expose schema via API,
- render using generic UI,
- execute through Dataset Planner,
- return typed Results.

---

## 8. Phase 3 — Recipe engine

### Deliverables

- Recipe registry,
- Recipe validation,
- Recipe selection by ID,
- pipeline execution mode,
- limited investigation mode,
- allowed Method enforcement,
- max step/query limits.

### Start with Revenue Investigation

Example behavior:

```text
compare revenue
  ↓
contribution by product/region/customer
  ↓
pick dominant branch
  ↓
inspect quantity/unit price/discount
```

### Important

The first version of `investigation` does not need a sophisticated autonomous agent.

It can use:
- deterministic heuristics,
- or a small LLM router constrained to allowed actions.

The runtime, not the model, remains authoritative.

---

## 9. Phase 4 — OLS or CEM

### Option A: OLS first

Pros:
- simpler,
- validates dataframe execution,
- easy statsmodels integration.

Cons:
- weaker stress test of causal semantics.

### Option B: CEM first

Pros:
- validates entity-grain extraction,
- matching/weights/diagnostics,
- demonstrates Method validation.

Cons:
- more implementation work.

Recommended sequence:

```text
OLS
then
CEM
```

unless causal analysis is the primary demo.

---

## 10. Phase 5 — Natural-language planning

Add:

### Semantic resolver

Input:
```text
“revenue”
```

Output:
```text
cube://production/sales/revenue
```

Resolver may only select from discovered catalog objects.

### Recipe router

Input:
```text
“Why did revenue fall last month?”
```

Output:
```text
revenue_investigation
```

### Planner

Produces typed AnalysisPlan.

### Narrator

Explains typed Result.

### Guardrails

- no invented semantic objects,
- no arbitrary Python,
- no arbitrary SQL as default path,
- refuse ambiguous high-impact resolutions,
- preserve Method interpretation semantics.

---

## 11. Phase 6 — Web UI

### Pages

```text
Sources
Recipes
Methods
Runs
```

Evals can initially be CLI/API-only if necessary.

### Sources

- connect Cube,
- show connection,
- show discovered semantic catalog.

### Methods

- registry browser,
- generated parameter/config form.

### Recipes

- create/edit Recipe,
- select semantic refs,
- choose related metrics,
- choose preferred dimensions,
- select allowed Methods,
- configure validators,
- configure execution limits.

### Runs

Show:
- question,
- plan,
- result,
- validation,
- provenance,
- generated semantic queries/compiled SQL where available.

### Important

Do not create bespoke pages for each Method.

---

## 12. Phase 7 — MCP

MCP should wrap the same application services.

Suggested tools:

```text
list_sources
get_semantic_catalog
list_methods
describe_method
list_recipes
describe_recipe
plan_analysis
run_analysis
get_run
get_result
```

Demo:

```text
User in ChatGPT/Claude
  ↓
“Why did revenue fall last month?”
  ↓
Decision Layer MCP
  ↓
Revenue Recipe
  ↓
Cube
  ↓
Typed result
```

---

## 13. Phase 8 — Evals

Minimal eval schema:

```yaml
question: Why did revenue fall in August?

snapshot: 2026-08-31

assertions:
  recipe: revenue_investigation

  semantic_refs:
    contains:
      - sales.revenue

  methods:
    contains:
      - query.compare
      - query.contribution

  forbidden:
    - raw_sql

  result:
    must_include_section:
      - largest_contributors
```

Run evals in CI later.

Start small:
- 10–20 questions for the demo business domain.

---

## 14. Suggested technology stack

This is a recommendation, not a hard requirement.

Backend:
- Python
- FastAPI
- Pydantic
- SQLAlchemy if persistence is needed

Statistical:
- pandas or Polars
- statsmodels
- scipy
- scikit-learn as needed

Worker:
- start synchronous or simple background queue
- do not add Celery/Temporal unless workload requires it

Database:
- PostgreSQL

Frontend:
- Next.js
- TypeScript
- a schema-driven form layer

MCP:
- Python MCP SDK or TypeScript depending on server stack

Packaging:
- Docker Compose for local demo

---

## 15. Persistence model

Keep initial tables simple.

Possible tables:

```text
sources
recipes
runs
results
eval_cases
eval_runs
```

Methods can initially be code/plugin registry rather than database rows.

### Run persistence

Store immutable snapshots of:
- Recipe version/content,
- Method versions,
- semantic refs,
- provider metadata,
- DatasetSpecs,
- validation,
- result,
- provenance.

Do not rely only on “current Recipe” to explain a historical Run.

---

## 16. Testing strategy

### Unit

- schema validation,
- provider capability checks,
- Dataset Planner,
- Method executors,
- validators.

### Contract

A Method plugin should pass:
- schema contract,
- result contract,
- serialization,
- error behavior.

### Provider

Use a small reproducible Cube fixture/project if possible.

### End-to-end

Test:

```text
question
→ semantic resolution
→ recipe
→ dataset planning
→ Cube
→ method
→ result
→ narration
```

### Regression eval

Separate agent/analytics behavior evals from software unit tests.

---

## 17. MVP anti-goals

Do not optimize early for:

- thousands of concurrent runs,
- arbitrary distributed compute,
- every statistical package,
- perfect auto-routing,
- autonomous agent depth,
- every semantic provider.

The MVP should validate the conceptual contract and repeated real use.

---

## 18. Product validation plan

The most useful signal is not “people liked the demo.”

Look for:

1. Did a user connect a real Cube model?
2. Did they create a Recipe?
3. Did they run it more than once?
4. Did someone else reuse the same Recipe?
5. Did users request new Methods or new Recipe capabilities?
6. Did they trust and inspect provenance?
7. Did they correct the system and want those corrections encoded?
8. Did they prefer this to repeatedly writing ad-hoc prompts/SQL?

Strong signal:

> “How do I encode our retention investigation playbook?”

Weak signal:

> “Cool project.”

---

## 19. First Codex implementation prompt

After reading all project docs, use:

```text
We are implementing the Decision Layer MVP described in the project docs.

Do not write feature code yet.

First:
1. restate the core domain model,
2. identify contradictions or underspecified contracts,
3. propose a concrete Python package/repository structure,
4. define the Pydantic models/interfaces for:
   - SemanticRef
   - SemanticProvider
   - ProviderCapabilities
   - MethodManifest
   - Recipe
   - DatasetSpec
   - AnalysisPlan
   - ValidationResult
   - Run
   - Result
5. propose the first 5 implementation milestones.

Preserve the architecture decisions in docs/DECISIONS.md.
Challenge any premature abstraction you find.
```

After review, a second prompt can be:

```text
Implement Phase 0 only.

Requirements:
- typed Pydantic models
- interfaces/protocols
- serialization tests
- no Cube network integration yet
- no LLM integration yet
- no Web UI yet

Update docs/DECISIONS.md only if implementation reveals a necessary architecture change.
```
