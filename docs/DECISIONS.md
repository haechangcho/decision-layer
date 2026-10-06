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

**Example clarification (2026-10-03):** `examples/chinook/` is the multi-table developer onboarding example, with an upstream release/checksum pin, PostgreSQL source tables, standard Cube joins/view, empty initial Recipes and independent SQL reference cases. `examples/online-retail/` is a larger real-transaction regression example; synthetic ecommerce remains useful for planted effects. Sample data is downloaded rather than committed. These are isolated development stacks, not bundled production data services or AI accuracy benchmarks. Canonical semantic references still name base members; the Cube provider selects a covering view without creating duplicate metrics.

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

The editor saves immutable new YAML versions under `DL_RECIPES_DIR`. Writes validate registered methods, declared roles/parameters, version and backward-only step expressions, and reject stale base versions. No database Recipe shadow is created. This is a Recipe authoring surface; it does not add a separate graph execution engine or alter semantic ownership. The `DL_RECIPE_ADMIN_TOKEN` write requirement was removed by ADR-038.

**UX clarification (2026-10-01):** Recipe authors first describe purpose, select semantic inputs and compose analytical steps. Canonical pipeline/investigation modes remain supported, but are not a mandatory initial UI choice. New Web Recipes use pipeline; existing investigations remain editable, and the editor does not convert modes destructively. The manifest controls basic versus advanced parameters. Routine parameters such as result count, ranking and minimum group size live in advanced settings; restoring a default removes only that explicit override. Existing inputs and investigation definitions survive editing. This authoring behavior is implemented and tested.

MCP clients may choose permitted invocation values through the same validators. This does not authorize a Web LLM, unrestricted parameter overrides or a conditional DAG engine. Fixed-versus-runtime parameter policy and resolved-value provenance still require a concrete contract before implementation.

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

## ADR-038 — Defer Recipe author authorization to application login

**Status:** Accepted (2026-10-01); supersedes the Recipe write-key requirement in ADR-035.

The Web no longer asks for a Recipe editing key, and `PUT /recipes/{name}` no longer checks `DL_RECIPE_ADMIN_TOKEN`. A writable `DL_RECIPES_DIR` remains required. The endpoint still resolves a Cube-accepted caller identity (or the explicitly enabled local service identity), validates the canonical Recipe contract and rejects stale base versions. This is **authentication through Cube, not Recipe author authorization**: any caller who can reach this API with valid Cube credentials can write Recipe files. In local anonymous/service mode, anyone who can reach the API can write them.

Until application login exists, deploy the Web and API only on localhost or a trusted private network; do not expose Recipe writes to an untrusted audience. Source administration retains its separate policy and key. The next authorization decision must integrate Authentik/OIDC, identify the application user independently of the Cube query identity, and require an author/editor role for Recipe writes across Web and direct REST/MCP callers. Read and execution permissions, logout/session handling, and audit attribution need explicit tests before public deployment. Do not reintroduce a shared Recipe key as a substitute for user authorization.

TODO before shared deployment:
- [ ] Integrate Authentik login and server-verified sessions; separate app identity from Cube query credentials.
- [ ] Enforce Recipe author/editor roles on Web, REST and MCP writes, including proposal approval.
- [ ] Test unauthorized writes, read-only users, session expiry and audit attribution end to end.

## ADR-039 — Record resolved Method parameters in each Run step

**Status:** Accepted (2026-10-01).

The common Run engine resolves omitted parameters from the registered Method manifest and stores the applied values in each executed `StepRecord.step.params`. `StepRecord.parameter_sources` records whether each value came from the Method default, a pipeline Recipe step or an explicit runtime request. A user-initiated step after a pipeline stops is a runtime request, even though the Run retains a Recipe snapshot. The Web exposes these values under Run evidence; older Runs without source metadata show an unknown source rather than a guessed one.

This is execution provenance, not a new override policy. Recipe-fixed versus runtime-selectable parameter contracts, minimum sample protections and AI override restrictions remain open U3 work and must be validated before those controls are offered. Method version remains in each StepRecord so historical values can be understood even after a manifest changes.

## ADR-040 — Readiness does not infer cross-cube time compatibility

**Status:** Accepted (2026-10-01).

Source readiness can confirm a time dimension when it shares the metric's canonical entity. It cannot conclude that time analysis is impossible merely because this local relation is absent: a Cube view or join can provide a usable date from another cube. The time check therefore reports `unknown` when other visible time dimensions exist but none can be confirmed by the local relation; `missing` means no time dimension is visible at all. Neither state authorizes a query. The Recipe run form offers visible date dimensions for explicit selection when metadata is inconclusive, and the provider verifies the actual query. This avoids treating a heuristic as semantic truth while preserving the Cube model as the owner of joins.

## ADR-041 — Recipe parameter policy is enforced by the shared engine

**Status:** Accepted (2026-10-02).

Registered Method manifests own parameter types, defaults and numeric bounds. The common Method registry validates these before execution; Web number controls use the same bounds. A Recipe may optionally declare `method_parameters.<method>.fixed` and `runtime_allowed`. Fixed literal values are merged into every invocation of that Method in the Recipe and cannot be overridden. When `runtime_allowed` is present, an explicit investigation/continuation step may supply only those parameter names; `null` means the existing unrestricted behavior and `[]` means no runtime-selectable parameters. Pipeline step parameters remain authored configuration, subject to fixed-value conflicts. The resolved Run step records `recipe_fixed` separately from Method defaults, Recipe step values and runtime requests.

Old Recipe files without this policy retain their behavior. The policy does not grant new semantic access, authorize arbitrary code or introduce a separate Web execution path. It does not yet solve step-specific policies for repeated uses of one Method, an organisation-wide policy service, or Run warnings for server-side row limits and exclusions. Those require separate evidence and contracts before broadening U3.

## ADR-042 — Unsaved Recipe previews are identifiable Runs

**Status:** Accepted (2026-10-02).

`POST /recipes:preview` takes an unsaved canonical pipeline Recipe, a target step index and a normal execution scope. It statically validates the Recipe, then the shared Run engine executes the prefix through that step with the caller's Cube credentials, Recipe filters, validators, parameter policy and query budget. Long previews use the ordinary background job/202 and Run polling behavior. The Recipe file is not written. The resulting Run is marked `preview`, owned by the caller and retains the candidate Recipe snapshot, steps, queries, validation and provenance. Runs lists and details label it as a preview; a preview does not offer a link to an unpublished Recipe or allow continuation.

Persisting previews gives a recoverable evidence trail and avoids a second ephemeral execution engine. It also means frequent previews consume Run storage; retention and pagination are U5 operations work, and previews must not be mistaken for approved Recipes or final analyses. Investigation Recipes have no fixed prefix and cannot use this endpoint. Promotion of preview or MCP Runs to Recipe still requires the separate U4 review/approval contract.

## ADR-043 — Draft Recipe versions are files and cannot execute

**Status:** Accepted (2026-10-02).

Recipe YAML gains a `status` of `draft` or `published`; missing status means `published` so existing files and API clients remain compatible. Every saved version stays immutable. The Web saves a draft version, then explicitly publishes it as a new immutable version after static and caller-visible semantic validation. A draft is returned by the dedicated editor/draft-list endpoints, but omitted from the default Recipe list and rejected by both named and version-pinned Run execution. Unsaved draft previews continue through ADR-042.

The file store is still the only Recipe source of truth (ADR-025). A publish request supplies the draft base version; a stale or already-published draft fails with 409 under the same file lock used for writes. Direct trusted `PUT /recipes/{name}` remains available for automation and may publish immediately for compatibility; the staged Web workflow does not imply application authorisation. Until ADR-038's Authentik roles are implemented, keep writes and publish endpoints on localhost or a trusted private network. Draft status is not an approval attestation. Git commits, PR review and multi-author approval remain separate future decisions.

## ADR-044 — Run steps become reviewable Recipe candidates

**Status:** Accepted (2026-10-02).

A caller who can read a non-preview Run may select successful steps in execution order and request a Recipe candidate. The API constructs a canonical draft Recipe; it does not save or publish it. The candidate keeps Method names, governed semantic bindings and explicitly sourced step parameters, while omitting the Run's period, shared filters, Method defaults and absolute comparison dates. Fixed drill paths require an explicit review note. The Web opens this candidate in the ordinary Recipe editor so the author must inspect and save it as a draft before publication.

The candidate records `origin_runs` as a traceable reference, not proof of approval or permission to read the source Run later. The endpoint rechecks current semantic access; invalid or failed steps cannot be promoted. This is a manual conversion of recorded execution, not an automatic proposal, graph dependency inference or a new execution path. Cross-user proposal inboxes, review roles, retention and source-Run deletion behavior remain U5 work and must follow ADR-038's application identity decision before shared deployment.

## ADR-045 — Run origin is an informational client hint

**Status:** Accepted (2026-10-02).

The canonical Run stores an `origin` (`web`, `mcp`, `api`, `python`, or `unknown`). Web and MCP send `X-Decision-Layer-Client` to the same REST API; the API accepts only `web` or `mcp` as hints, otherwise records `api`. Direct Python engine calls record `python`. Existing stored Runs without this field deserialize as `unknown`. Runs UI can label and filter MCP exploration without changing the shared execution engine.

This header is **not authenticated provenance**: any REST client can claim it, so it must never grant access, approve a Recipe, or identify an accountable human. Run ownership still follows ADR-029. MCP clients do not currently supply a trustworthy conversation/session ID; grouping Runs into a conversation is deferred rather than approximated with a process lifetime or timestamp. Proposal review and approval require the separate application identity and authorization contract in ADR-038.

## ADR-046 — Preserve the original question for ad hoc Method Runs

**Status:** Accepted (2026-10-02).

An ad hoc Method request may include the user's original question. REST and MCP pass it to the shared Run engine, which stores it in `AnalysisPlan.question` alongside the executed Method and semantic bindings. It is optional for existing API clients and historical Runs. The Web shows a missing-question label for older Runs instead of inferring a question from the Method or metric. MCP tool guidance asks the client to send the original question, but a client may omit it; this is user-provided context, not verified intent.

Run details lead with question, governed metric, Method, period, date basis and result. Query specs, semantic references, Method versions and resolved parameter sources remain available as folded execution evidence. Hiding raw evidence from the first view does not remove it from the Run record or weaken validation. This adds no LLM to the Web and does not let the question redefine semantic objects or execution contracts.

## ADR-047 — Group Recipe-free MCP exploration by question

**Status:** Accepted (2026-10-02).

When no Recipe fits, MCP may start a Recipe-free Run with the original question and scope using `start_analysis`, execute registered Methods through `run_step`, and finish with `complete_run`. This exposes the existing REST/Run engine lifecycle rather than creating a second execution path. The Run records each Method result, semantic binding, validation and query as a separate ordered step, so the Web can show the full exploration under one question. A one-off `run_method` remains available and still produces its own completed Run.

No Recipe means no organization-authored Method or metric allow-list; normal Method contracts, Cube access, query/step budgets and fail-closed validation still apply. The MCP client's Method choice and final narrative are not independently verified or approved. The step graph denotes execution order only, not causal or data dependencies. Turning such a Run into a Recipe remains the explicit review flow of ADR-044, not automatic publication.

## ADR-048 — Record step purpose separately from analytical evidence

**Status:** Accepted (2026-10-02).

`PlanStep.purpose` is optional, short client-authored text describing which part of the original question the Method is intended to answer. MCP passes it through the canonical Run step request; the shared engine stores it with the executed step. The Run UI may use this text to explain Method selection, but must label it as intent rather than a validated finding. Older Runs and Recipes without a purpose remain valid. The Web can fall back to a generic Method description, not fabricate question-specific reasoning.

The Run detail leads with the question, answer, and a read-only metric-to-Method graph; selecting a step reveals its result and advanced evidence. The graph describes semantic bindings and execution order, not an editable Recipe or causal dependencies. Promotion still requires deliberate Recipe draft review under ADR-044. This changes presentation and optional provenance context, not Method execution or semantic ownership.

## ADR-049 — Explicit descriptive peer comparison

**Status:** Accepted (2026-10-04).

`query.peer_comparison` compares a single dimension/value with explicit peer conditions and the accessible overall population, using the same period and shared filters. The subject's value is measured inside its peer context. Both benchmarks exclude the subject; no organization hierarchy is inferred. Shared filters fixing the subject are refused so a drill-down filter cannot silently collapse the comparison population. Cube evaluates each metric at its governed aggregation; the Method does not average group rates or redefine joins. Missing or undersized populations fail comparison under the configured minimum row count.

The initial Method is descriptive: it reports values, row counts and differences, not an outlier probability, significance test, risk-adjusted performance or causal effect. Sums are warned as population-size dependent. Drill-down selection, repeated cases and case-mix differences preclude claiming wrongdoing from a high rate. Statistical anomaly judgments require a separately validated design. Dimension references in typed parameters are included in result provenance and access rechecks.

Reviewed Methods may use installed statistical/ML packages and report their versions through `MethodOutput.runtime`. This is not a runtime plugin installer or permission for generated analysis code. Execution still uses the canonical registry/context.

### Default developer sample

Complete Journey replaces Chinook as the recommended first environment, based on the original Databricks data-preparation example but using an original PostgreSQL loader and Cube model. Eight tables are downloaded from dunnhumby's official 2023 archive with a fixed checksum; source files are not committed or relicensed.

The official archive's demographic codes remain codes. Relative DAY is mapped to an explicitly artificial calendar for Cube time queries. Retailer receipts retain the publisher's meaning, not customer-paid revenue or profit. Campaign contacts and coupon redemptions remain separate facts; coupon-product and placement tables are loaded but are not blindly joined to transaction measures. This sample is observational, not causal ground truth, and Databricks' simplified campaign attribution is not adopted as an identification assumption.

### Sample consolidation (2026-10-04)

Complete Journey is the sole deployable sample. Chinook, Online Retail and synthetic ecommerce stacks, loaders, domain-specific live tests and their CI references are removed to avoid competing onboarding paths. Historical ADR references above describe earlier experiments, not currently available files; their results are not Complete Journey benchmark evidence. Local downloaded data, personal Recipes and Docker volumes are not deleted. Self-contained synthetic metadata and deterministic unit/causal tests remain contract fixtures, not another sample environment. The runnable Method contribution template remains independent of the sample.

## ADR-050 — Register a recorded procedure with its execution settings

**Status:** Accepted (2026-10-04); supersedes ADR-044's lossy candidate conversion and mandatory draft-only Web path.

Run-to-Recipe conversion preserves every recorded parameter (including resolved defaults and absolute comparison dates), semantic bindings, step purposes, shared filters and Method versions. Recipe `default_scope` records the source period and time dimension; omitted execution fields inherit these defaults across REST, Python and MCP, while explicit REST null clears a default. Shared filters become Recipe required filters. A pinned step refuses execution if its recorded Method version is no longer installed. Replaying a procedure does not freeze source data or semantic definitions.

`POST /runs/{id}/recipe` validates a completed, non-preview Run's successful steps and current semantic access, then saves a published Recipe through the canonical file store. The explicit **Register as Recipe** action authorizes this publication; repeated calls return the same source-Run Recipe. No background promotion occurs. The existing candidate endpoint remains available for editing or selecting successful steps before saving. Both paths use the same lossless conversion. Existing file-version conflict protection and ADR-038's local-only authorization boundary still apply.

Run details put registration beside the question and expose results, applied settings, queries and readable source names as peer views. Raw identifiers remain inspectable. Required Method inputs precede optional preview controls in the editor; a drill-down can preview all data without choosing an arbitrary date range. Cube sample models are split by source table without changing governed members, joins or metric definitions.

## ADR-051 — Delete a Recipe without deleting its Runs

**Status:** Accepted (2026-10-04).

An explicit, confirmed Web action or `DELETE /recipes/{name}?base_version=...` removes every published and draft YAML version of a Recipe from the configured file store. This is an exception to version retention, not permission to overwrite a version. The latest version is checked under the existing file lock; stale requests return 409. Files are matched by their declared Recipe name, including hand-authored files in subdirectories. Recorded Runs retain their Recipe snapshots, results and provenance. Deleted Recipes disappear from discovery and cannot start new executions. Git-backed installations record ordinary file deletions; repository commits remain externally managed. Authorization follows the existing local authoring boundary in ADR-038.

## ADR-052 — Typed sample dates and provider-owned period hints

**Status:** Accepted (2026-10-04); refines ADR-049's example calendar storage.

The Complete Journey importer adds stored generated PostgreSQL DATE columns for purchases, redemptions and campaign start/end, retaining source day indices. The fixed day-1 origin remains 2000-01-01 so existing Run queries and Recipe periods retain their meaning. An idempotent, transactional migration upgrades existing volumes; sample dates do not claim real purchase years. Date conversion, date extents and source-specific knowledge belong exclusively to the sample loader and Cube model.

A semantic time object's optional `metadata.suggestedDateRange` provides a YYYY-MM-DD period suggestion. Optional `calendarType: mapped` identifies a transformed calendar; its meaning is explained in the provider's object description. Web may prefill an untouched period from this hint, with a unique same-cube hinted time dimension as a suggestion when no explicit selection exists. Saved Recipe defaults and user selections take precedence. MCP forwards these optional hints without interpreting a domain, computing dates, changing execution parameters or weakening validation. Hints are not freshness guarantees or restrictions on selectable dates. No sample name, business domain or fixed year is present in the execution engine or generic Web/MCP logic. Providers without hints retain existing behavior.

---

## ADR-053 — Run owners may delete execution records

**Status:** Accepted (2026-10-04)

`DELETE /runs/{id}` removes one Run and its recorded results from the Run store after the caller is checked as its owner. A shared viewer receives the same 404 as for a missing Run. An active background job returns 409 so its worker cannot recreate a deleted record. The Web asks for confirmation and explains that queries and validation evidence disappear with the Run. Deleting a Run does not delete a Recipe already registered from it; that Recipe is a separately owned file. This is a deliberate user initiated deletion, not a retention policy or automatic cleanup.
---

## ADR-054 — Structured Run conclusions and informational AI attribution

**Status:** Accepted (2026-10-05)

Runs optionally persist a caller-authored conclusion with a short answer, findings linked to zero-based recorded step indices, and limitations. The engine checks that linked steps exist; it does not verify the narrative or promote it into a Method finding. Existing `summary` remains supported, and structured answers also populate it when no legacy summary is supplied. Historical text is not heuristically split, regenerated, or overwritten. Engine warnings remain visible independently of caller-authored limitations.

Start, ad hoc, step and completion requests accept optional client/model attribution. Run initiation, each explicit step and the conclusion keep separate snapshots so a later model is not attributed to earlier work. MCP reads the actual client implementation name/version from request context when available; model provider, ID and revision require explicit reporting. Missing metadata stays absent. These are informational, untrusted caller assertions, not authentication, approval, a reproducibility guarantee or proof of model identity (ADR-045). They never grant permissions or enter promoted Recipe parameters. All surfaces use the same request models and Run engine; no Web LLM is added (ADR-021).

Run presentation separates the answer, evidence-linked findings, limitations, primary results, diagnostics, applied inputs/options, provider requests and provenance. Generic artifact renderers use typed result shapes rather than sample-domain names. Raw requests, original precision and raw result records remain inspectable. A descriptive Method is never given a fabricated significance judgment. Older Runs remain readable without invented model metadata.

---

## ADR-055 — A common conclusion lifecycle for every Run

**Status:** Accepted (2026-10-05); refines ADR-054.

MCP `complete_run` requires a structured conclusion rather than merely recommending one. Its instructions apply to all registered Methods, investigations and pipeline Recipes, not particular sample questions. The tool remains exposed in the Method-only MCP profile. The canonical engine creates a source-labelled `execution` summary whenever an ad hoc, pipeline, preview or failed Run terminates without caller narration. These summaries record execution status and links to recorded results, never invented question answers, significance, causes or business advice.

Completed Runs without a previous narrative may receive one structured caller conclusion through the same completion API. This annotates completed evidence without re-executing it or changing its execution finish time. Existing caller conclusions or legacy summaries cannot be overwritten through completion; ownership and busy checks still apply. Caller submissions are always marked `caller`, irrespective of a supplied source label.

Historical terminal Runs without structured conclusions normalize to the same execution-summary contract on read. Their original `summary` remains unchanged, available in an explicit original-text view, rather than being heuristically split or presented as newly authored structured findings. New terminal Runs persist the shared structure. One common Run answer component renders every Method, Recipe and origin; the distinction between a caller conclusion and non-narrated execution stays visible. No Run IDs, sample values or domain-specific conclusions are embedded in this lifecycle, and no server/Web LLM is added.

---

## ADR-056 — Self-hosted MetricFlow and explicit provider metadata

**Status:** Accepted (2026-10-06). Extends the Cube-first integration scope at the user's request.

The Complete Journey example selects Cube through the default Compose override, or dbt through explicit `compose.yaml` and `compose.dbt.yaml` files. It no longer starts both providers by default. `DL_DEFAULT_SOURCE_PROVIDER` selects the initial connection without locking the selector or overriding saved settings. The dbt project models all six analytical tables used by Cube, including campaign descriptions, contacts and redemptions. Contact periods refer to campaign start dates; no unobserved contact timestamp or household event date is fabricated.

Native dbt count metrics declare their own counts and native ratio metrics supply decomposition. Custom annotations remain optional: `count_measure` associates another metric with its actual sample count; numerator/denominator hints expose the structure of derived percentage metrics. Redundant metric-kind and duplicate denominator annotations are removed from the example. Example calendar caveats remain in dataset documentation rather than dimension descriptions.

Sources supports Cube and self-hosted dbt MetricFlow, with one active connection and separately preserved provider settings. Environment overrides remain provider-scoped; `DL_SOURCE_PROVIDER` may lock the selection. Existing Cube variables and persisted settings remain compatible. Requests bind the selected provider before credentials are used; background workers inherit that request context so a concurrent connection change cannot redirect an in-flight query or bearer token.

The optional `metricflow` environment runs an HTTP gateway using pinned dbt Core, dbt-postgres and dbt-metricflow packages. The gateway accepts canonical DatasetSpecs, resolves fields against the discovered semantic catalog, and invokes MetricFlow's actual planner and execution engine. No generated SQL, project path, code or arbitrary Jinja is accepted from callers. PostgreSQL is the verified warehouse. dbt Cloud APIs are a separate, unimplemented adapter; their URLs are not compatible with this gateway.

Catalog measures explicitly declare queryable dimension references, their default time basis and a provider-declared count metric. Cube maps its existing native declarations into this contract. MetricFlow uses its discovered queryable dimensions and dbt `config.meta.decision_layer` for optional sample-count and decomposition declarations. Metric meanings and joins remain provider-owned. Methods and the Web no longer infer time/sample-count relationships from the word `cube` or matching URI path segments. Fully qualified Recipe references remain stable across connection changes; switching a source never rebinds a saved Recipe automatically. Legacy short refs keep their store's default namespace and should be replaced with explicit refs for multi-provider installations.

The first MetricFlow adapter supports aggregate drilldown, trend, peer comparison and categorical-condition CEM. Entity extraction, unsupported filter operators and unsupported date bases fail closed. Results are capped at 50,000 rows and retain provider-native requests and optional compiled SQL. A matched observational comparison does not become a causal proof because two engines agree.

Gateway bearer tokens authorize one configured warehouse profile; they do not authenticate arbitrary JWT subjects or groups. The adapter declares credential-based identity, and Run ownership uses a provider/instance-scoped token digest after the gateway accepts it. Anonymous use requires explicit local-development configuration. Per-person/RLS enforcement and authentik integration remain separate work; no impersonation claims are forwarded to the warehouse. The Complete Journey example adds dbt views over the existing PostgreSQL tables and a gateway on loopback port 4100 without replacing the Cube service or source data.

---

## ADR-057 — Connect unmodified native semantic models

**Status:** Accepted (2026-10-06). Supersedes the custom analytical metadata provisions of ADR-056 and the Cube ratio-meta interpretation of ADR-022/023.

Connecting an existing semantic layer must not require Decision Layer-specific annotations. The example Cube and dbt models contain no such metadata. Adapters use native declarations, not custom numerator/denominator/count hints, to establish analytical semantics. Generic provider metadata remains preserved for evidence; it does not redefine a metric's statistical meaning.

MetricFlow exposes native ratio components through `type_params` and native count metrics through their aggregation. Cube `/meta` does not expose a calculated number's numerator and denominator structurally. Neither a neighboring count nor a plausible formula/value proves the sample population of a metric. Cube count measures identify themselves, but sum, average, distinct-count and calculated measures do not inherit a sibling row count.

Existing metric references, percentage calculations and values are preserved. Descriptive analysis remains available without sample counts. Sample-size checks and statistical analysis that require unknown sample semantics must not produce guessed evidence; the derived coupon-rate example refuses CEM. Restoring that statistical example requires verified native semantic information and unit-aware validation, not mandatory provider annotations or expression guessing. Existing Runs retain their original evidence unchanged.

---

## ADR-058 — Official dbt API for product connections; selectable local examples

**Status:** Accepted (2026-10-06). Extends ADR-056; hosted dbt is a product connection, not a future placeholder.

Companies connect their existing dbt Semantic Layer through its public GraphQL API using a deployment endpoint, environment ID and bearer token. The `dbt` provider is separate from `metricflow`, the bundled local example gateway. Cube and local dbt examples remain equally visible choices in the README and documentation quickstart. The local dbt example requires no paid account and does not certify or emulate the hosted GraphQL service.

The adapter implements native metric/dimension discovery, catalog pagination, canonical aggregate query translation, `createQuery`, bounded status polling and paginated results. It records environment ID, native request, provider query ID, available SQL and page counts. Known execution-error details are retained in Runs so remote query IDs survive failures. Authentication/GraphQL errors fail closed; requests do not forward tokens through redirects or expose raw provider error payloads. Categorical filters are generated from validated canonical operators and values; arbitrary SQL/Jinja is not accepted.

No customer project files, warehouse credentials or Decision Layer annotations are required. Native SIMPLE type does not establish sum/count aggregation; unavailable sample semantics remain unknown. Entity extraction and unsupported operators fail explicitly. Official API contract tests include the shared Method -> Run -> Recipe path; a separately opt-in authenticated smoke test validates a real deployment when credentials are available.

Tokens retain the existing per-request model: Web keeps its token in session storage and MCP uses `DL_TOKEN`. The provider accepts the credential before its digest is used as a Run owner; a shared token is a shared identity. This does not implement employee login or authentik. Source endpoint and environment settings may be saved or fixed through provider-scoped environment variables. A request binds both source and environment before execution, including background work.

Reference: https://docs.getdbt.com/docs/dbt-apis/sl-graphql

---

## ADR-059 — MCP execution requires a question-scoped Run

**Status:** Accepted (2026-10-06). Refines ADR-032, ADR-054 and ADR-055 for MCP execution.

MCP exposes one Method execution tool, `run_step`, requiring an existing Run ID and a step purpose. The independent `run_method` tool is removed. Recipe-free analysis uses `start_analysis`; Recipe analysis uses `start_run`. The Method-only profile hides Recipe tools but retains analysis start, step, polling and completion. The canonical engine rejects MCP-origin ad hoc execution before creating a record, blank original questions and steps without purposes. Explicit duplicate step IDs are rejected; absent IDs are assigned in recorded execution order. These are engine rules shared by REST and MCP, not instructions that a model may ignore. Client-origin labels remain informational, not a security boundary.

MCP Runs remain open after Method or pipeline execution. Completion requires recorded steps, a nonblank answer and nonblank findings with existing step-index links. The engine does not verify narrative truth or whether a caller copied the original question faithfully. Forgotten completion leaves persisted evidence in an open Run, rather than manufacturing a completed answer. Web shows conclusion waiting, permits the owner to record a conclusion, and only then permits one-click registration of the complete procedure. Successful steps from an unfinished analysis may still be reviewed as a Recipe draft.

Existing historical Runs are preserved, not grouped heuristically. Python/Web/REST standalone Method execution remains supported; the revised MCP lifecycle intentionally breaks clients that cached the removed tool and requires a fresh tool discovery after restart. A chat host does not supply a trustworthy user-turn identifier, so distinct explicit start calls are distinct Runs; the product never merges by text similarity, elapsed time or a shared service identity. Method choice and interpretation still require judgment, but Method execution cannot implicitly create a new Run for each step.

---

## ADR-060 — Recipes preserve selection rules, Runs preserve resolved evidence

**Status:** Accepted (2026-10-06). Supersedes ADR-050's unconditional publication of resolved Run settings; extends ADR-039 and ADR-041.

A reusable procedure distinguishes literals, declared typed runtime inputs, and typed selections from an earlier successful step. A parameter source specifies an earlier step ID, a manifest-declared `ranked_groups` output, `first` selection, and a projection (`path`, `condition`, or `parents`). These projections separate a nested branch from a peer-comparison subject and its peer conditions. No source can execute code, SQL, Jinja, or an arbitrary JSON selector. Existing explicit `$scope` and `$steps` expressions remain compatible; they are not proofs of complete highest-group selection.

Methods opt into named selection outputs. The ordinary drilldown exports eligible candidates in ranking order at unrounded precision, independent of displayed `top_n` and whether another drill dimension exists. The conservative group-query cap marks the population incomplete. Missing, unsuccessful, empty, incomplete, or invalid outputs cannot select a group. A tied leading score requests explicit input without issuing downstream queries. Period-contribution drilldowns do not yet export this output, so unsupported selections fail closed. There is no last-Run fallback.

The canonical engine records the requested step separately from the resolved step, with source, projection, selected score, ranking direction and completeness evidence. Runtime inputs are declared by the Recipe, type-checked before execution, and snapshotted into Run scope. All surfaces use this resolver and revalidate resolved semantic references with current provider credentials. This is a bounded sequential procedure contract, not a general workflow DAG.

Run promotion preserves recorded rules and stable step IDs. A selected subset missing dependencies is rejected. Old pipeline Runs may recover rules from their immutable Recipe snapshot; old exploratory literals are never assigned inferred dependencies by matching values. Selection-sensitive fixed groups and periods require review. The Web presents the observed value alongside a fixed/previous-result/runtime choice; canonical registration requires acknowledgment when review notes exist. An explicit literal remains valid after review. Run periods and extra shared filters are execution context and are not silently promoted into permanent defaults or required filters. Already-authored Recipe required filters, input schemas and parameter policies are retained. Branch selections stay in step parameters so an overall comparison retains the global execution scope.

Existing Runs and Recipe versions are immutable. A known literal procedure may be rewritten as a reviewed newer Recipe version using explicit user intent, never a repository-wide heuristic migration. Repeated registration is idempotent only for the same reviewed specification; divergent changes require versioned editing.

---

## ADR-061 — One-click Run registration defaults to runtime selections

**Status:** Accepted (2026-10-06). Supersedes ADR-060's mandatory promotion review and literal-copy default for direct registration.

Registering a completed Run is one explicit action, without a configuration dialog. Recorded typed rules and declared runtime inputs are retained. Unprotected literal group parameters become runtime selections, not remembered winners. This is a policy for constructing a new procedure, not evidence that the historical analyst intended a particular dependency.

The bounded promotion policy connects matching semantic dimension paths to the most recent earlier declared selection output. A peer subject uses the selected condition; its peer population uses that subject's parent path when the declared dimensions match. Global Run filters are never replaced with branch conditions. No winner-value matching, natural-language inference, provider-specific business names or server LLM are involved. Ordinary historical drilldowns may use their registered Method's native dimension/path contract; unsupported outputs are not guessed. Ranking follows the upstream step's configured criterion; future execution still rejects incomplete, empty or tied selections.

When an earlier output cannot supply a group, the new Recipe declares a required typed runtime input without a literal default. MCP callers supply it when starting the Recipe; Web exposes the same input contract. Registration therefore does not silently freeze a target or invent an analytical relationship. Explicit fixed Method policies remain fixed; custom configurations are available through the optional editor. Other analytical parameters retain their recorded settings.

Default registration returns an already-published Recipe from the same Run without overwriting later versions. Custom-spec changes still use explicit versioned editing. Existing Runs and Recipe files are not migrated or mutated.

---

## ADR-062 — Declarative Method authoring inputs

**Status:** Accepted (2026-10-06). Extends ADR-060/061; no custom frontend plugin runtime.

Method manifests declare input labels, semantic reference kinds, visibility, display groups and allowed source policies. The shared editor renders these contracts; contributors do not implement React panels. Canonical `configure_step`, exposed through `POST /recipes:configure-step`, constructs explicit Recipe bindings and typed sources. Previous-result defaults use the most recent earlier declared ranked-group output; peer-population defaults follow another declared input's parent projection. Missing required targets become declared runtime inputs without remembered defaults. These rules are deterministic authoring defaults, not inferred historical intent or an LLM planner. The execution resolver still rejects incomplete, empty and tied selections.

Description and primary metric are the general Recipe settings. Source summaries appear before source controls. Per-step analytical choices remain editable; Method-wide policies, budgets and input-schema authoring are available in the separate code view. Existing explicit parameters and policies are preserved. New metadata is optional for older contributions, and does not change numerical Method versions or provider semantics.

---

## ADR-063 — Required-input editor; execution conditions on demand

**Status:** Accepted (2026-10-06). Refines ADR-062's disclosure model.

The ordinary step editor displays required semantic roles and explicitly basic parameters, not every engine option. Drilldown ranking, direction and branch-source controls move to the complete code view. Branch context remains a read-only explanation of the actual stored rule; it is not another required form. Optional role catalogs and a generic advanced-options panel are removed. Metric overrides remain an explicit action. Hidden, fixed and nondefault values are preserved rather than silently replaced or migrated.

Result checking is one action. Only when execution needs a period or declared runtime inputs does it reveal those conditions. A Method declares `requires_period`; period-dependent boolean parameters use their declared meaning. The editor does not choose a period based on Method-name branches or introduce a Web LLM. Canonical preview, validation, provenance and selection refusal rules remain unchanged. Providers still own semantic meaning; simplifying authoring never means removing engine safety checks.

A multi-value semantic role may declare an `editor_parameter` for its effective scalar choice. The manifest validator requires a matching string parameter, role and semantic kind. Drilldown uses this to show its current dimension without asking users to edit the historical dimension list; existing lists and selectors are preserved until explicitly changed.

---

## ADR-064 — Explicit periods and server-owned execution policy

**Status:** Accepted (2026-10-06). Extends ADR-021/039/042/060 and refines ADR-063.

An omitted or null period is unresolved, not implicit all-data authorization. Canonical scope accepts an explicit date range, all-period choice, or bounded relative rule. Existing non-null `date_range` requests remain valid. Recipe and organization defaults resolve before querying; null no longer clears them. Explicit choices override defaults, and conflicting declarations are rejected. Relative rules resolve against execution time in their declared timezone; no sample calendar or data-end inference exists in the engine. Requested rule, actual dates, caller-reported source and server policy revision are recorded separately.

The common engine checks periods before analysis/freshness queries. Waiting Runs store pending intent, not fake result steps. Owner-only revision-checked scope submission resumes the same pending execution. Scope changes after execution or on an active job require a new Run. Web asks inline on demand, MCP uses `set_run_scope`, and all interfaces share the same contract. Caller source labels do not prove user approval. No server LLM or approval bypass is introduced.

`DL_EXECUTION_POLICY` controls explicit all-period allowance, period length, application deadlines, query counts and result row counts. General installs disallow all-period execution by default; the bundled example explicitly opts in. Dataset requests are checked again so a Method cannot silently omit the chosen period or bypass range limits with its own period parameters. These are execution boundaries, not warehouse scan-cost guarantees. App timeouts do not claim warehouse cancellation; provider-native estimate/cancel and role-based approvals remain follow-up work. MVP concurrency is one API process, not distributed workers.

Old Runs remain unchanged and missing period provenance is shown as unknown. Run-to-Recipe registration preserves already-declared Recipe period rules, never silently copying exploratory execution dates into defaults. This intentionally changes legacy null-period execution to a waiting request and must be documented for API/MCP callers.

---

## ADR-065 — Verified primary-unit averages in CEM

**Status:** Accepted (2026-10-06). Extends ADR-005/020/028/057; does not weaken unknown-sample refusal.

`causal.cem@1.1.0` accepts an optional explicit `sample_count` for provider-native average outcomes.
The average and count must share a provider-declared, queryable primary key. The count must be a native
row count, not a guessed sibling sum or distinct count. The Method requests bounded aggregate rows grouped
by that key and conditions, then verifies one counted row and one finite non-null outcome per unique unit.
Duplicate units, nullable outcomes, overlapping treatment groups and potentially truncated results refuse.
Matching uses unit means and target-composition weights. Continuous-outcome confidence intervals and
significance are not implemented: the result explicitly records `statistical_judgement: not_tested` and
never uses the existing proportion test for an average, even when values happen to lie in 0..100.
This minor version changes the installed Method version; historical Runs are untouched and older pinned
Recipes must be deliberately reviewed before upgrading.

The local MetricFlow adapter preserves native aggregation declarations from the deployed dbt-generated
semantic artifact before its parser rewrites count to sum(CASE ...). It exposes a primary key only when
a native primary entity has an equivalent, engine-queryable dimension. No Decision Layer annotations or
SQL-expression guessing are added. Hosted dbt GraphQL metadata currently does not establish average
aggregation/primary-unit/count semantics, so this path remains unavailable there until native metadata
can verify those contracts. Publishing the dbt example model alone is not a claim of hosted API support.

The Complete Journey example adds a shared PostgreSQL materialized campaign-household outcome model,
consumed by Cube and dbt, refreshed by the existing importer. Campaign windows, population eligibility,
pre-treatment bands and zero-purchase definitions belong to that example model, never to Method code.
It includes previously active households, dataset-complete 30-day windows and an other-campaign exposure
diagnostic. Select one campaign for a household comparison; multiple campaigns repeat households and
are not independent household observations. Global date coverage does not prove individual follow-up,
target-list membership is not actual receipt, and non-targeted does not mean unexposed to all marketing.
Observed matching remains an association, not known causal ground truth. No scheduler is introduced.

---

## ADR-066 — Save calculated procedures independently of analytical validity

**Status:** Accepted (2026-10-06). Extends ADR-060/061; does not change execution refusal.

Run-to-Recipe conversion accepts successful steps and refused steps with a primary analytical
output and an explicit failed validation. Such steps completed calculation but cannot support
a valid conclusion for that population. Their procedure is reusable on other execution contexts.
Needs-input, failed and refusals without this calculated evidence still require editing or exclusion.
The Web and canonical conversion enforce the same distinction, including refusal-only Runs.
Method versions, semantic validation, parameters, thresholds and result statuses are unchanged.
The candidate explains that registration is not result approval. A pipeline still stops on refusal;
later exploratory steps are not inferred as conditional fallback branches. No new workflow engine
or remembered Run filter defaults are introduced.
