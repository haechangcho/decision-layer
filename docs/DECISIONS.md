# Decision Layer — Architecture Decision Log

This file records important product and architecture decisions, including ideas deliberately rejected or postponed.

Do not silently reverse these decisions. If new evidence justifies a change, add a new ADR that supersedes the old one.

---

## ADR-001 — Cube first

**Status:** Accepted

### Decision

Cube is the first first-class semantic provider.

MVP should optimize for a high-quality Cube connection and discovery/execution experience before adding other semantic layers.

### Why

- One deep integration is more useful than several shallow ones.
- Cube provides the semantic objects and downstream-consumption model needed to validate the product thesis.
- It lets the product prove the key flow: semantic model -> dataset planning -> analytical execution.

### Constraint

Core contracts must remain provider-neutral enough to support future providers.

---

## ADR-002 — Semantic definitions remain in the semantic layer

**Status:** Accepted

### Decision

Decision Layer Recipes and Methods reference semantic objects but do not redefine their business logic.

### Example

Allowed:

```yaml
metric: cube://production/sales/revenue
```

Not allowed:

```yaml
metric:
  name: revenue
  sql: SUM(price * quantity)
```

### Why

Duplicated semantic logic creates drift and defeats the purpose of a semantic layer.

---

## ADR-003 — Method and Recipe are different core concepts

**Status:** Accepted

### Decision

A **Method** is a reusable atomic analytical capability.

A **Recipe** is reusable procedural analytical knowledge, typically organization-specific.

### Example

Method:
```text
query.drilldown
```

Recipe:
```text
Revenue Investigation:
- compare periods
- contribution by product/region
- inspect quantity/price/discount
```

### Why

A senior analyst's investigation procedure is not a new statistical algorithm.

Conflating them would create method proliferation and poor reuse.

---

## ADR-004 — Recipe is a stronger product object than a large algorithm catalog

**Status:** Accepted

### Decision

Product value should not be framed primarily as “supporting many statistical algorithms.”

The stronger use case is encoding and executing institutional analytical procedures.

### Why

- CEM/OLS/DiD already exist in mature libraries.
- Organizational procedural knowledge is often undocumented and difficult for junior analysts/agents to reuse.
- Meta and Anthropic both emphasize reusable procedural analytics knowledge.

---

## ADR-005 — Dataset Planner is a core subsystem

**Status:** Accepted

### Decision

Methods do not directly query Cube.

Methods declare dataset requirements; the Dataset Planner converts them into provider-level queries.

### Why

Different analyses require different data shapes:

- drill-down: aggregate,
- OLS: tabular,
- CEM: entity-level,
- DiD: entity x time panel.

This is one of the main places where Decision Layer creates value beyond wrapping statistics libraries.

---

## ADR-006 — Push down computation when possible

**Status:** Accepted

### Decision

Filtering, grouping, and aggregation should remain in the semantic provider/warehouse whenever possible.

### Why

Pulling large raw datasets into the Decision Layer worker by default will not scale.

Methods declare one of:
- `semantic_pushdown`,
- `dataframe`,
- `hybrid`.

---

## ADR-007 — Natural language does not generate arbitrary execution code

**Status:** Accepted

### Decision

LLMs route questions to:
- existing semantic objects,
- registered Recipes,
- registered Methods,
- typed Plans.

They do not normally invent Python or unrestricted SQL for execution.

### Why

The product thesis is governed, reproducible analytics, not code-generation convenience.

---

## ADR-008 — Support deterministic and constrained agentic execution

**Status:** Accepted

### Decision

The runtime supports two broad modes.

1. **Pipeline** — fixed analytical procedures such as CEM or simple DiD.
2. **Investigation** — iterative analysis where the next step depends on previous results.

### Constraint

Investigation must be bounded by:
- allowed Methods,
- semantic scope,
- query limits,
- step limits,
- validation rules.

---

## ADR-009 — Validation and provenance are first-class

**Status:** Accepted

### Decision

A result is incomplete without:
- validation outcomes,
- provenance,
- method/recipe versions,
- semantic references,
- freshness where available.

### Why

Analytics AI must be reviewable. A plausible but wrong number is especially dangerous.

---

## ADR-010 — Trigger engine is not core

**Status:** Accepted

### Decision

Do not build a trigger/scheduler/event orchestration engine in MVP.

### Why

“When should this analysis run?” is an orchestration concern.

Existing systems can call Decision Layer:
- Airflow,
- Dagster,
- Prefect,
- cron,
- webhooks,
- agents.

Decision Layer should expose deterministic run APIs.

### Future

A lightweight automation module may be reconsidered only after real user demand.

---

## ADR-011 — Decision Graph is not MVP

**Status:** Accepted

### Decision

Do not implement KPI/driver/hypothesis/decision graph functionality in MVP.

### Why

It introduces a separate ontology problem:
- decomposition,
- association,
- hypothesized cause,
- supported cause,
- decisions,
- evidence.

This can easily turn the product into a knowledge-graph platform before the core analysis layer is validated.

### Preparation

Use stable IDs so a future graph can reference:
- semantic objects,
- Recipes,
- Runs,
- Results.

---

## ADR-012 — Superset is not part of the product architecture

**Status:** Accepted

### Decision

The intended analogy is:

```text
Cube -> Superset
Cube -> Decision Layer
```

not:

```text
Cube -> Decision Layer -> Superset
```

### Why

Decision Layer should be an independent downstream semantic consumer, not a BI publishing bridge.

---

## ADR-013 — Do not build a notebook product

**Status:** Accepted

### Decision

Power users should access Decision Layer through Python SDK from:
- Jupyter,
- Databricks,
- Hex,
- VS Code,
- other notebooks/IDEs.

### Why

Building a notebook UI is unrelated to the core differentiation.

---

## ADR-014 — Web UI is schema-driven

**Status:** Accepted

### Decision

Adding a Method should not require a new bespoke frontend page.

### Preferred

Generic components:
- semantic field pickers,
- enum/select,
- number,
- date,
- bins,
- metric/dimension/entity selectors.

### Avoid

```text
CEMPage.tsx
DIDPage.tsx
OLSPage.tsx
```

---

## ADR-015 — No arbitrary frontend plugins in MVP

**Status:** Accepted

### Decision

Method packages cannot ship arbitrary React components in MVP.

### Why

This creates unnecessary:
- security,
- dependency,
- build,
- sandboxing,
- frontend compatibility problems.

Use generic primitives or Python/API escape hatches.

---

## ADR-016 — Domain is not a required core object

**Status:** Accepted

### Decision

Do not require a heavyweight `Domain` object in MVP.

Use lightweight metadata first:
- namespace,
- tags,
- owner,
- scope.

### Why

Meta/Anthropic show that bounded context matters, but that does not imply Decision Layer needs a first-class Domain entity on day one.

### Future

Promote to a Domain/Domain Pack only if users need:
- shared validators,
- shared references,
- ownership boundaries,
- scoped evals,
- reusable source/context bundles.

---

## ADR-017 — Raw query-history RAG is not the core context strategy

**Status:** Accepted

### Decision

Historical SQL may be mined offline to suggest:
- Recipes,
- common filters,
- common dimensions,
- documentation.

Do not make raw query-history retrieval the primary runtime context mechanism.

### Why

Structured, curated procedural context is more reliable and maintainable than dumping large corpora of historical work into the agent.

---

## ADR-018 — Git/versionability is a long-term requirement

**Status:** Accepted

### Decision

Recipes, validators, evals, and references should be exportable/versionable as files.

### Why

Institutional analytical knowledge should be reviewable and change with the data model.

The Web app may manage these objects, but must not become the only durable store of meaning.

---

## ADR-019 — Method semantics control allowed interpretation

**Status:** Accepted

### Decision

Method outputs carry interpretation semantics.

Examples:
- OLS without identification strategy: association, not causation.
- CEM: causal estimate conditional on assumptions and observed covariates.
- drill-down/contribution: descriptive decomposition.

### Why

The Narrator/agent must not make stronger claims than the Method supports.

---

## ADR-020 — Fail closed when requirements are not satisfied

**Status:** Accepted

### Decision

The system should refuse or warn rather than improvise when:
- fields are missing,
- provider cannot produce required grain,
- causal timing is incompatible,
- sample/overlap assumptions fail,
- semantic resolution is ambiguous.

### Why

Trust is more valuable than producing an answer to every question.

---

## ADR-021 — No server-side LLM in MVP; investigation is a server-enforced session

**Status:** Accepted (2026-09-29)

### Decision

Investigation-mode Recipes run as a Run session: the caller (an MCP client such as Claude, or a person in the Web UI) proposes each step; the server authorizes it against the Recipe's allowed Methods, semantic scope, step/query limits and validators, then executes it. Decision Layer itself does not call an LLM in MVP.

### Why

ARCHITECTURE §16 (server Router/Investigator/Narrator) and §18 (Claude calls Decision Layer over MCP) would otherwise stack two LLMs. A prior Decision Graph experiment showed registered procedures + server instructions + a small tool set keep an MCP client on the governed path. A server-side LLM can be added in Phase 5 if needed.

---

## ADR-022 — Ratio decomposition requires provider-declared parts

**Status:** Accepted (2026-09-29)

Contribution / mix-rate decomposition of a ratio measure needs its numerator and denominator. Cube `/meta` does not expose measure SQL, so a ratio is only decomposed when the measure's provider metadata declares `{numerator, denominator}`; otherwise the Method fails closed (ADR-020). The declaration lives in the semantic layer, consistent with ADR-002.

---

## ADR-023 — Semantic refs name base cube members; views are a query-time concern

**Status:** Accepted (2026-09-29)

Refs are `cube://{instance}/{cube}/{member}` for **base** members. At query time the Cube provider routes through the smallest view exposing every requested member (views carry curated joins and access), falling back to base cubes, and maps results back to base refs.

---

## ADR-024 — Callers' credentials pass through to the provider

**Status:** Accepted (2026-09-29)

Decision Layer forwards the caller's bearer token to Cube, so Cube's own access rules apply. A service credential (JWT signed with the Cube API secret, configured groups) is a local/dev fallback only.

---

## ADR-025 — Recipes are files; the database stores execution records

**Status:** Accepted (2026-09-29)

Recipes, validator configuration and evals are YAML/JSON files owned by the deploying organisation (Git-first, ADR-018), loaded from `DL_RECIPES_DIR`; none ship with the core (see ADR-028). The database stores Runs (with their Results) only.

---

## ADR-026 — Cube OSS standard features only; provider hints are optional

**Status:** Accepted (2026-09-29)

Decision Layer uses only the standard Cube REST API (`/meta`, `/load`, `/sql`) and standard model syntax. Optional hints such as `hierarchies` or measure `meta` may improve behaviour but no Method may require them; drill order defaults to the Recipe's `preferred_dimensions`.

---

## ADR-027 — Measures of joined cubes are allowed at entity grain

**Status:** Accepted (2026-09-29) — supersedes the entity-grain restriction noted under ADR-023

Cube aggregates each cube's measures by that cube's primary key before joining ("multiplied measures"), so a measure of another cube evaluated per entity key (e.g. a child-cube count per parent key) does not fan out. The provider therefore allows such measures at entity grain; when Cube has no join path between the members, its error is reported as `CAPABILITY_MISSING`. This enables unit-level Methods (CEM unit path, OLS) with treatments or outcomes from joined cubes.

---

## ADR-028 — The core is domain-neutral; domains are examples

**Status:** Accepted (2026-09-29)

Decision Layer is intended to be open source. Code under `src/` — Method manifests, MCP server instructions, validator and limitation messages, comments — uses structural language only (measure, dimension, unit, count × per-count value), never a business domain's vocabulary. Domain material (Recipes, eval scenarios with expected values, semantic model notes) lives under `examples/<domain>/`; tests may use an example domain because its expected values are known. `tests/unit/test_domain_neutral.py` guards `src/`.

---

## ADR-029 — Runs belong to their caller; identity comes from a provider-accepted token

**Status:** Accepted (2026-09-29)

- **Authentication.** Requests carry `Authorization: Bearer <token>`, passed through to the semantic provider (ADR-024). Requests without it are rejected (`401 UNAUTHENTICATED`) unless `DL_ALLOW_SERVICE_CREDENTIALS` is set, which is for local development only: every such request shares one service identity.
- **Identity.** Decision Layer does not verify signatures itself. The caller's identity is the `sub` (or `email` / `user_id`) of a token the provider has accepted — `discover()` succeeded with it — so a forged subject is rejected by the provider. Tokens without a subject cannot own runs (`403`).
- **Ownership.** A Run belongs to the caller who started it. Listing returns only the caller's runs; reading, continuing or completing another caller's run answers `404`, the same as a missing run.
- **Sharing.** The owner can share a run read-only with subjects (`"*"` = any authenticated caller). A shared run exposes results computed with the owner's permissions, so it is only shown to a viewer whose own catalog contains every semantic object the run used; otherwise `403`. Row-level differences between owner and viewer are not detected — sharing is an explicit act by the owner, like sharing a report.

---

## ADR-030 — Analyses run as background jobs; requests wait briefly, then answer 202

**Status:** Accepted (2026-09-29)

Unit-level Methods (CEM unit path, OLS) and pipelines can take tens of seconds and are partly CPU-bound. Every execution (ad-hoc Method run, pipeline start, investigation step) therefore runs as a job in a worker thread with its own event loop, so the API's event loop stays responsive.

- The request waits up to `wait` seconds (query parameter; default `DL_REQUEST_WAIT_SECONDS`, 25; max 300). Finished in time → the usual 200 response. Otherwise `202 {run_id, status: "running", poll}`; the client polls `GET /runs/{id}/result` (202 while running, the Result when done, the recorded error otherwise).
- Job state lives on the Run (`running`, `error`) in the run store, so polls work from any process. A run executes one job at a time (`409 RUN_BUSY`).
- Jobs are in-process (`DL_JOB_WORKERS`, default 4) and do not survive a restart: on startup, runs left `running` get `error.code = INTERRUPTED` (ad-hoc runs and pipelines become `failed`; an investigation stays open). A shared queue is the step up for multi-process deployments.
- The MCP server waits 45 s per call and offers `wait_for_run`; the web UI polls.

---

## ADR-031 — English is the source language; translations are catalogs

**Status:** Accepted (2026-09-29)

User-facing text in `src/` — error and validation messages, warnings, artifact titles, Method manifests, MCP instructions and tool descriptions — is written in English and wrapped as `_("… {placeholder} …", placeholder=value)`. Translations live in `src/decision_layer/i18n/<locale>.json`, keyed by the English text with the same placeholders. The API picks the language per request from `Accept-Language` (default `DL_LOCALE`, else `en`) and carries it into background jobs; manifests are translated when served; the MCP server uses `DL_LOCALE`. Messages are rendered when produced, so a stored run keeps the language it ran in. `tests/unit/test_i18n.py` fails on Hangul in code, missing or unused catalog entries, placeholder mismatches, and locals named `_` (which would shadow the translation function).

---

## ADR-032 — Period-change judgements stay on the server; `compare` folds into `trend`

**Status:** Accepted (2026-09-30)

**Question.** Is a separate `compare` Method needed, or can the MCP client judge period changes from raw series?

**Experiment** (`examples/ecommerce/evals/experiment_compare.json`, 5 scenarios × 3 repeats, recipe tools off, Claude via the CLI):
- A — current Methods, strict number rule.
- B — `drilldown`, `trend` (raw series only: no test, no day adjustment, no decomposition), `contribution`, `cem`; relaxed rule (simple arithmetic allowed, judgements only from result fields).

| Scenario | A | B |
|---|---|---|
| Q3 return rate +0.07 pp — noise (CI includes 0) | 3/3 | **0/3** |
| Q3 sales +0.65% — all from 92 vs 91 days | 3/3 | 3/3 |
| Top shoe seller — not significant after selection | 3/3 | 3/3 |
| Category → seller drill-down (S017) | 2/3 | 3/3 |
| Free shipping, matched (+1.57 pp) | 3/3 | 3/3 |
| **Total** | **14/15** | **12/15** |

Numbers were derivable from tool results in every run of both variants; path consistency was 0.87 (A) vs 0.73 (B).

**Findings.**
- Without a server-side test the client explained noise every time. It even stated that no test had been run, then attributed the rise to channels anyway. It never computed significance from the unit counts it was given.
- B handled unequal periods only because another result carried the `comparable_periods` warning; the judgement still came from the server.
- The client's own arithmetic (per-day values, shares) was correct and disclosed.

**Decision.**
1. Keep period-change judgements server-side, but not as a separate user-facing Method. When `trend` gets two periods (and when `drilldown` compares periods, absorbing `contribution`) it reports the overall change with its test (count proportions), the per-day comparison for unequal periods, and — for measures with declared parts — the factor decomposition. `compare` and `decompose` are then removed.
2. Adopt the relaxed MCP number rule: simple arithmetic on returned numbers is allowed and must be disclosed; significance, relatedness and data-quality judgements come only from result fields.
3. The eval grader's phrase checks proved fragile (a negated "…is not the cause" matched a banned phrase; "cannot be determined" passed a noise case). Scenarios now use affirmative banned phrases and require an explicit non-significance statement.

**Confirmation** (same scenarios after consolidating to `query.drilldown` 2.0, `query.trend` 1.0 and `causal.cem`,
relaxed rule by default): 15/15 answers correct, including the noise case 3/3; every number derivable from results;
path consistency 0.87. The period-change scenarios now take a single `query.trend` call.

---

## ADR-033 — Web-editable source configuration with environment overrides

**Status:** Accepted (2026-09-30); U1 source settings and readiness API implemented.

The user selected web editing with environment variables taking precedence. Source connection settings may be stored in the server database. This narrowly supersedes ADR-025's execution-records-only database rule; Recipes remain organization-owned files.

- Environment overrides are reported per field and locked in the Web UI.
- Persisted development API secrets must be encrypted with a deployment-managed key kept outside the database. Never return plaintext secrets in configuration responses or include them in logs, diffs or Run snapshots.
- Caller bearer tokens continue to pass through per request (ADR-024). The connection screen may keep an operator-entered token in that browser tab's session storage; it is never stored as a shared source credential in the server database. API-secret service credentials remain a local/development fallback.
- Connection testing and saving are separate operations. Source administration requires an explicit server-side authorization policy; Cube query access alone does not authorize changing the shared connection.
- `DL_SOURCE_CONFIG_KEY` is the Fernet key provisioned outside the database. `DL_SOURCE_ADMIN_TOKEN` is a separate shared-settings capability; the browser keeps it in session storage and sends it only to source-admin endpoints. Missing configuration disables source editing. Deployments should rotate the admin token independently of Cube credentials.
- This decision does not approve or implement the proposed KPI graph, which still needs a scoped decision under ADR-011.

## ADR-034 — Graph-based Method configuration (superseded)

**Status:** Superseded by ADR-035 (2026-10-01).

The Web configures canonical Method invocations through a React Flow canvas: a semantic metric connects to analysis nodes. Basic controls use business labels; full manifest parameters remain in advanced settings. Executions use the existing Method API and produce ordinary Runs, including asynchronous polling and server-provided input candidates.

This decision captured an incorrect UI placement. It is retained as history; its Method-centered graph is removed.

## ADR-035 — Recipe owns the method graph

**Status:** Accepted (2026-10-01).

Methods are fixed registry entries. The Recipe editor composes them into an ordered pipeline or declares methods available to an investigation, then stores method roles and parameters in the Recipe's canonical `PlanStep` format. Web, API, Python and MCP execution continue through the same Recipe and Run engine.

The editor saves immutable new YAML versions under `DL_RECIPES_DIR`. Writes require a distinct `DL_RECIPE_ADMIN_TOKEN`, validate registered methods, declared roles/parameters, version and backward-only step expressions, and reject stale base versions. No database Recipe shadow is created. This is a Recipe authoring surface; it does not add a separate graph execution engine or alter semantic ownership.

**UX clarification (2026-10-01; implementation pending):** Recipe authors first describe purpose, select semantic inputs and compose analytical steps. Canonical pipeline/investigation modes remain supported, but are not a mandatory initial UI choice. Routine parameters such as result count, ranking and minimum group size belong in advanced settings with versioned defaults; existing explicit values must survive editing. MCP clients may choose permitted invocation values through the same validators. This does not authorize a Web LLM, unrestricted parameter overrides or a conditional DAG engine. Fixed-versus-runtime parameter policy and resolved-value provenance require a concrete contract before implementation; see the updated product UX plan.

## ADR-036 — Token-free local Cube connection is opt-in

**Status:** Accepted (2026-10-01).

**Superseded by ADR-037 (2026-10-01):** Endpoint discovery was removed. Explicit development-only anonymous authentication remains supported. Enterprise OIDC and service-account authentication are not implemented capabilities.

For local development, the Web may offer a one-click Cube connection that discovers a Cube endpoint reachable from the Decision Layer server. If the Cube accepts unauthenticated API requests, Decision Layer sends no Authorization header; if a Cube API secret is configured, the existing service-credential fallback signs the request. The user does not need to mint or paste a token for this local path.

- This behavior is available only when `DL_ALLOW_SERVICE_CREDENTIALS=true`; the setting remains false by default and must not be enabled as a production shortcut.
- An unauthenticated Cube gives every Decision Layer user the same Cube access. Cube deployments with access controls should use the advanced caller-token or API-secret configuration instead.
- Endpoint discovery is server-side because the browser's `localhost` is not necessarily the API process's `localhost`. Environment-provided `CUBE_API_URL` remains authoritative and is never replaced by discovery.
- This changes only credential selection and connection setup. Cube remains the source of semantic definitions and access policy; authenticated caller tokens continue to pass through unchanged (ADR-024).

## ADR-037 — Explicit source URL and authentication policy

**Status:** Accepted (2026-10-01); connection UI/API implemented, enterprise OIDC pending.

Source setup displays the Cube API URL and authentication mode. Only that URL is called; there is no endpoint scan or credential fallback to other hosts. Source settings still require the distinct administrator capability and environment overrides remain authoritative.

Connection tests and execution use the same credential selector. In `token` mode a missing or rejected bearer token fails without service-secret fallback. `none` explicitly selects an anonymous development identity and never derives a user identity from an unverified incoming token. `none` and `api_secret` require `DL_ALLOW_SERVICE_CREDENTIALS=true`. Existing secret-based development deployments retain service fallback, while an explicitly provided caller token continues to pass through in authenticated modes.

Tests verify catalog access, not successful data queries. The UI invalidates the test when connection inputs change and exposes catalog navigation after saving. Authentik OIDC, token renewal and separation of application identity from service query identity are not implemented.
