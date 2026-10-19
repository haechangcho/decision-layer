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

---

## ADR-067 — Explicit comparison groups in the shared Recipe editor

**Status:** Accepted (2026-10-06). Refines ADR-062/063.

Optional scalar roles may declare a shared `exclusive_group` to represent alternative
semantic inputs in one catalog picker. CEM's dimension/measure group-splitting roles
use this declaration; exactly one is required when validating a Recipe. Basic group
parameters declare their associated `semantic_role`, so the shared renderer places
target/comparison definitions directly after the selected criterion, before matching
conditions. Boolean, explicit values, exclusions and numeric ranges use typed controls,
not Method-specific React components or inferred business meaning. Changing the criterion
clears unfixed associated definitions; fixed policies prevent changing their criterion.
Existing hidden parameters, sample bindings and historical Runs remain intact. Empty,
nonfinite, mixed and inverted group definitions fail canonical parameter validation.
The numerical Method version and statistical thresholds do not change. CEM's existing
provider/metric capability checks still apply; a catalog entry alone is not a promise
that the requested comparison can execute.

---

## ADR-068 — Paired groups and verified authoring count defaults

**Status:** Accepted (2026-10-06). Extends ADR-062/065/067.

The shared editor places target and comparison definitions side by side and shows the
actual boolean or one-sided numeric opposite when the existing Method rule determines it.
It does not invent categorical values or rename boolean values into domain concepts.
An unresolved multi-category comparison remains an execution-time question.

A count role may declare `default_binding: unit_count`. Canonical `configure_step`
accepts the caller-visible catalog and writes an explicit count binding only for a
native average with a declared primary unit and exactly one same-unit native row count
(count aggregation, with its self count declaration). It never uses names, sibling sums,
distinct counts or guessed relationships. Ambiguous or absent candidates require input.
Existing explicit choices remain intact. REST configuration uses current provider credentials;
Python callers may pass the same catalog. This is an authoring default, not a new runtime
inference path. ADR-065's one-row/non-null outcome checks still run and may refuse even a
unique candidate (including filtered counts). Statistical thresholds are unchanged.
The normal editor hides an established count binding, keeps it in YAML/provenance, and
shows a corrective prompt for missing or incompatible bindings. Historical Runs and
saved Recipes are not migrated or automatically rewritten.

---

## ADR-069 — Separate recorded intent from execution scope

**Status:** Accepted (2026-10-07). Extends ADR-060/061.

Run promotion preserves the original step purpose verbatim and records `purpose_context`
as `source_run`; explicitly authored procedural descriptions use `procedure`. This is
descriptive provenance, not an executable period or filter rule. The Web separates
original intent from the current Run scope; MCP returns both context and actual scope.
Editing a description marks it as procedural. Historical promoted Recipes without
this marker use their recorded `origin_runs` for presentation only; no stored records,
filters, periods or selection rules are rewritten. Natural-language dates are not parsed
or stripped to guess a reusable intent.

Population comparisons preserve the semantic layer's aggregation over each population,
not an inferred average across members. Results expose this basis and state that the
Method does not perform significance tests even if counts exist. Calculation and
validation thresholds do not change. Historical result views use existing aggregation
metadata to explain the same contract without modifying evidence.

## ADR-070 — Governed lookup, Recipe candidates and goal evidence

**Status:** Accepted (2026-10-07). Extends ADR-007/020/021/030/064.

- Aggregate lookup is the registered `query.aggregate` Method, not an arbitrary SQL
  or Python escape hatch. REST preview uses the same Run engine and requires an
  explicit period decision; entity analysis remains a registered Method responsibility.
- `/recipes:search` and MCP `find_recipes` return candidates, not an automatic selection.
  Search combines text overlap with goals, semantic references, configured capabilities
  and interpretation. Execution rechecks the selected version and compatibility.
  Structural compatibility does not verify the business meaning of natural language.
- MCP starts require typed goals; subsequent steps require goal links. Completion
  records an outcome for every goal. Supported outcomes require successful results
  with relevant references, actual capabilities and appropriate interpretation.
  Caller-written narrative and missing-Method diagnoses are not independently verified.
- Methods declare `provides` and optional parameter-dependent `provides_when`; results
  report only capabilities actually provided. Lookup cannot prove a causal effect.
- Provider executions are persisted before execution, including failure/interruption.
  Failed attempts consume Run budgets, including legacy Runs. Identical explicit step
  IDs are retry-safe under a per-Run lock. This counts logical executions, not every
  provider-internal polling or pagination HTTP request.
- One pipeline Recipe invocation may coexist with exploration before and after it.
  `use_recipe` attaches it to an open Run, preserving its snapshot and namespacing
  step references. Shared scope, access, metric and parameter restrictions still apply.
  Nested/multiple invocations and attaching investigation Recipes are deferred.
  Follow-up execution can be disabled by policy.
- Unresolved goals remain input needed, unsupported, blocked or inconclusive.
  Unsupported/blocked-only questions may finish without a query or resolved period.
  Historical Runs use optional additive fields and are not rewritten.
- Missing-Method outcomes may prepare a public GitHub issue draft using only explicitly
  supplied public text. Run data, questions, queries and references are not copied.
  The user reviews and submits on GitHub. No automatic publishing, credential storage
  or arbitrary Method execution is introduced.

## ADR-071 — Recipe reuse context and recorded selection

**Status:** Accepted (2026-10-07). Extends ADR-060/069/070.

Run promotion preserves `source_question` separately from an authored routing objective.
Historical promoted Recipes without that field use their description as source context
when presenting candidates, without rewriting YAML or stripping dates from prose.
Candidate information includes the executable procedure, role bindings, settings,
runtime shared period, actual defaults, required filters and literal Method periods.
Source questions and source step purposes are provenance, not execution constraints.
Explicit defaults and fixed Method settings are never erased or generalized.

MCP starts recompute up to five currently visible candidates. Starting without a Recipe
requires a concrete skipped `recipe_review` for those candidates. A selected Recipe
records the selection reason; later `use_recipe` appends the new decision. The Run keeps
the candidate snapshot and reasons so subsequent edits cannot alter this evidence.
Reviews are caller-reported, not proof of semantic suitability or verified explanations.
No unrelated Recipe is forced and no server LLM, date parsing or generated code is added.
Other canonical callers may provide reviews; historical Runs remain readable with none.
Shared access checks also cover references in candidate snapshots.

Recipe-disabled MCP profiles retain read-only candidate search for recording reasons,
but cannot execute Recipes. Updating MCP clients requires restarting their tool session.

## ADR-072 — Step periods and observed date coverage

**Status:** Accepted (2026-10-07). Clarifies ADR-032/064.

Trend and drilldown apply an explicit current period even without a comparison.
The current period must be within a bounded Run period; expanding it requires updating
the Run scope. Comparison periods may precede the Run period and remain subject to
execution policy and query limits. Results record the actual series period and its source.

Calendar completion means the end date has passed, not that ingestion is complete.
Observed date coverage queries the same metric time dimension and scope/branch filters,
using a provider-declared count when available and otherwise the metric itself. This
bounded query uses the existing execution policy, access checks and query budget.
Unsupported daily grouping or unavailable observations yield an unknown warning.
An earlier observation warns about comparison coverage, without claiming missing
ingestion: inactivity and missing ingestion cannot be distinguished. Existing Runs
are not rewritten and no provider model annotations or domain rules are introduced.

## ADR-073 — Remove the custom MetricFlow gateway

**Status:** Accepted (2026-10-08). Supersedes the local gateway portion of ADR-056/058.

Product connections are Cube REST and the official dbt Semantic Layer GraphQL API.
This provider-availability decision is superseded by ADR-096 for the initial product.
Remove the custom MetricFlow gateway, provider, optional dependencies, Docker stack,
UI option and gateway-specific tests and instructions. The local retail example runs
Cube only. dbt SQL/YAML models remain reference definitions for an existing dbt
deployment, not a bundled hosted API or proof of hosted adapter compatibility.

MetricFlow and dbt semantic interfaces are open source; dbt's service layer and
Semantic Layer APIs are proprietary hosted components, as documented in the
[official architecture](https://docs.getdbt.com/docs/use-dbt-semantic-layer/sl-architecture).
Decision Layer does not implement a replacement semantic API or claim that a local
gateway verifies enterprise authentication and warehouse behavior.

Retain the official adapter and its GraphQL contract tests and opt-in authenticated
smoke test. Never rewrite historical Runs or rebind Recipe references implicitly.
Unsupported saved gateway configurations fail with an explicit error; configure
Cube or official dbt through the canonical source API. Existing data volumes are
not deleted. No changes to Method, Recipe or Run execution contracts are required.

## ADR-074 — Fail-closed CEM inference and range validation

**Status:** Accepted (2026-10-08). Tightens ADR-020/028/065.

`causal.cem@1.1.1` does not identify a count percentage from numerical coincidence.
Intervals require a provider-declared count/count ratio whose denominator is the
matching count. The Method queries the declared numerator in the same scope and
checks finite integer counts, numerator <= denominator and the percentage against
100 * numerator / denominator. Unknown definitions or other scales remain descriptive
matched comparisons without interval artifacts. This does not establish independent
sampling, identify causal effects, or support continuous-outcome inference.

Failed matching quality checks expose no significance artifacts. Outcomes must be
finite and counts non-negative integers. Explicit ranges must be finite, strictly
increasing, and refer to numeric matching conditions. Ambiguous exclusion/range
group combinations refuse instead of potentially querying overlapping populations.
Balance reports identify their basis as `coarsened_strata`; zero weighted imbalance
does not mean continuous covariates within a bin are identical.

Historical Runs and pinned Recipes are not rewritten. Review pinned Method versions
before upgrading. The additional numerator is subject to existing access, scope and
query limits. No provider-specific model annotations or client-only calculation are added.

## ADR-075 — Reviewed semantic improvements and linked reanalysis

**Status:** Accepted (2026-10-08).

Runs can contain proposed semantic improvements tied to a recorded analysis goal.
Keep the inspected evidence, rationale, suggested improvement and typed requirements;
unknown references remain unset. Absence from the caller's catalog does not distinguish
missing definitions from denied access. Input, permission, Method and data-quality
problems must not be automatically classified as semantic-model defects.

Only the Run owner can review, dismiss, check or retry a proposal. Review is an
authenticated owner action, not proof of domain validity or a separately verified
human approval. MCP exposes proposal recording, rechecking and retry, but no approval
tool. Original proposals, review changes, catalog checks and retry links remain in
the Run JSON document. No extra database or semantic definitions in Recipes are added.

Rechecking refreshes caller-scoped catalog metadata (including Cube's cached meta),
checks visibility, kind, declared type/aggregation and requested entity/time metadata.
This is NOT a dry execution, proof of join/grain validity or confirmation of causal
assumptions. Normal Method, dataset, permission and period checks still run on execution.
Connection failures never become a successful check. Models are edited externally.

Retry requires a confirmed proposal and repeats the metadata check using current
credentials. A new Run preserves the question and analytical goals, snapshots the
reviewed requirements and links back to the original. Explicit period changes are
allowed; replacing goal semantics or rewriting old evidence is not. A chosen Recipe
uses canonical start/selection/version checks. Without a Recipe, the new investigation
awaits fresh Method choices; old literal result selections are never blindly replayed.
The Web labels this as starting reanalysis, not completed analysis. The API/MCP client
can select a suitable Recipe or continue the new Run through normal execution APIs.

Revision checks and existing per-Run locks prevent stale single-process edits; this
does not claim distributed transaction/idempotency support across multiple API workers.
GitHub submission, model auto-editing, PR orchestration and a separate proposal inbox
are out of scope. Private model suggestions remain in the Run, not public issues.

## ADR-076 — Record blocked analysis without asking users to manage Runs

**Status:** Accepted (2026-10-08). Extends ADR-059/069/075.

Missing semantic definitions can be found before any Method executes. Asking users
whether to create a Run or record a gap makes product internals their responsibility.
`POST /analyses:blocked` / MCP `report_analysis_blocked` records the original question,
all goal outcomes, caller-reported evidence, proposed semantic requirements and a
conclusion in one Run document write. New records cannot report supported goals
without executed evidence. Missing semantic outcomes require typed proposals;
input, access, Method and execution failures must not become model proposals.
Existing partial analyses are finished in their owned open Run with validated
evidence links; their question, goals and earlier steps cannot be replaced.

No provider query, substitute metric, model edit, approval, GitHub submission or
new analytical calculation occurs. Proposals remain unconfirmed. Diagnostic intent
is recorded even when no executable scope or Recipe is available; execution policy
still applies if reanalysis starts. The record is not proof that caller explanations
or catalog absence are correct. MCP returns a Run URL (`DL_WEB_URL`, local default
http://localhost:3000) and requires recording before an inability-to-answer response.

This removes multi-tool bookkeeping once invoked, not LLM host behavior entirely:
a server cannot observe natural-language questions or replies that never reach its
tools. Client instructions and real-client regression testing are still required.
Do not claim guaranteed automatic capture of every chat or user approval.

## ADR-077 — Review-only semantic model drafts

**Status:** Accepted

Semantic improvement proposals can include bounded provider-specific YAML text,
its API-based rationale and unresolved physical-schema details. These are
caller-proposed external-edit drafts, not canonical semantic definitions,
validated model patches or executable code. Decision Layer never applies them.
Unknown columns, model names, joins and grain must remain explicit placeholders.
API catalog visibility cannot establish the underlying warehouse schema.

One proposal may reference additional recorded goals through `related_goal_ids`
when they require the same missing definition. Blocked recording validates their
semantic-missing outcomes and rejects duplicate coverage. Historical proposals
are not merged by fuzzy text similarity. Existing Runs default to no drafts or
additional goals; the Web can show clearly unbound dimension-format examples.
Review, caller-scoped recheck and linked reanalysis remain the ADR-075 flow.

## ADR-078 — Model suggestions without a Web approval workflow

**Status:** Accepted

The Run page shows semantic improvement suggestions, YAML and evidence only.
It does not ask users to approve suggestions, link definitions, recheck metadata
or launch a linked retry. Users edit their semantic layer externally and ask
again; normal discovery and execution validation apply to the new analysis.
This supersedes the default Web journey in ADR-075, not model ownership or
execution safeguards. Existing review/retry APIs and historical records remain
compatible; no model is changed and no approval is inferred automatically.

## ADR-079 — Python-first Method development helpers

**Status:** Accepted (2026-10-10).

Methods remain reviewed Python implementations with one manifest and the ordinary
Registry/ExecutionContext contracts. `MethodSession` simplifies caller-scoped catalog
discovery, explicit local registration, direct execution evidence and Recipe preview.
Direct runs stay in the caller's event loop for breakpoints and create no stored Run;
previews use the existing RunEngine, workers and session-local memory Run store.
No code, credentials or evidence is installed or uploaded to a remote server.
The helper is for trusted local Python, not a code sandbox. Live data still requires
provider credentials and dataset validation. Direct runs have explicit scopes and
the existing policy's period, query, row and deadline bounds.

Strict fixture providers match complete expected DatasetSpecs to independently
specified responses or errors. They are test tools, not semantic providers shipped
as product connections or proof of warehouse aggregation/access correctness.
Multi-query peer comparison is the first executable example, without Web/Docker.
Implementations live in Python modules; generated notebooks import them and contain
no saved outputs. Standard pytest remains the contribution test interface.

The shared Registry rejects undeclared artifact types for all callers, extending
its existing selection/capability checks. Aggregate, trend and drilldown manifests
now list artifact types already emitted; calculation behavior and versions are
unchanged. Historical Runs are not rewritten. Payload-shape and numerical correctness
remain Method-specific tests; this does not claim a complete artifact data schema.

An in-browser Python runtime, package installer, plugin marketplace and local-to-Web
Run synchronization are deferred until concrete contributor demand justifies them.

## ADR-080 — Fresh-clone contributor paths and explicit code ownership

**Status:** Accepted (2026-10-10). Refines ADR-079.

README routes Method contributors to Python-only fixture tests before Web/Docker.
Standard pip/pytest/npm commands remain supported; Make only wraps repeated commands.
First-Method and peer-comparison examples each own their ordinary Python modules and
pytest tests. Optional notebooks import implementations. Remove the duplicated
percent-cell files and notebook generator. The default suite includes example tests.

Expose authoring types from `decision_layer.methods`. Keep built-in implementations
flat under that package, with an explicit registration list. Preserve logical Method
IDs, versions and analytical behavior; source imports using former query/causal
subpackages must update. Separate the Method contract from Registry execution checks.
No dynamic package installer or new execution framework is introduced.

Move reusable test providers/client factories to `tests/support`; tests no longer
import other test modules or execute example scripts with runpy. Use standard package
imports and pytest importlib collection for duplicate example test filenames.

REST assembly stays in api/app.py; resource route groups share authentication and
response helpers and canonical engine/services. Recipe semantic validation is reused
by authoring and promotion. Pure execution policy helpers have their own module;
the RunEngine retains orchestration. Recipe/Run Web components live with their feature,
while shared controls and renderers stay in components.

Current product/architecture pages replace historical speculative implementation
outlines. Detailed Method metadata is a reference page, not the first tutorial.
Keep historical ADRs, licensed/public sample data definitions and analytical/access
regressions. This changes contributor organization, not stored Runs, Recipe semantics
or provider ownership. No data volume or local credential is deleted.

## ADR-081 — Typed function authoring and canonical input maps

**Status:** Accepted (2026-10-12). Extends ADR-079/080; class Methods remain supported.

Reviewed async Python functions may declare typed semantic roles, ordinary typed
parameters and a Table/TimeSeries/Estimate return type. `@method` generates the
existing MethodManifest and a Method adapter; it never registers on import.
Registration validates IDs/defaults. Unsupported annotations fail explicitly.
Installed reviewed bootstrap code registers implementations; requests cannot upload
Python or install packages. The class API remains the escape hatch for additional
artifacts, selections and specialized contracts.

Python, REST and MCP accept measures/dimensions/entity input maps, normalized into
canonical bindings. Legacy bindings still work. Run step maps normalize after owner
and Recipe authorization, preserving idempotent canonical requests. Web uses the same
generated manifests. Statistical variable roles may explicitly accept measures and
dimensions; the catalog determines which fields become provider measures versus
grouping dimensions. A unit is a provider-declared primary dimension, never an
inferred URI/name. Cube validates actual joins; extracted analysis keys must be unique.

Common aggregate/entities helpers apply mandatory scope filters, explicit current or
comparison periods, policy bounds, optional SQL evidence and query labels. Current
periods cannot expand scope. Complete extraction requests a sentinel row and refuses
overflow rather than accepting top-N samples. Panel needs use the existing entity
DatasetSpec plus TimeScope granularity; uniqueness is unit × bucket. No panel product
object, separate planner or semantic formula/join definition is introduced. Catalog
search remains caller-visible; declared/unknown relationships are discovery evidence,
not authorization or proof of join support.

Bounded condition, filters, date_ranges and analysis-design parameters extend the
shared schema. Registry checks, Recipe serialization, REST/MCP and generic Web inputs
share these types. Typed results validate their JSON payloads; existing class Method
artifacts retain compatibility. Historical Runs and pinned Recipes are not rewritten.
Existing aggregate/trend/drilldown/peer/CEM calculations and versions remain intact.

Optional OLS, DoWhy-adjusted differences, EconML DML and simple two-group/two-period
contrasts use ordinary installed libraries. Missing/incompatible dependencies refuse
before data queries and never trigger installation. Tested numerical constraints and
a separate optional CI job cover the causal stack on Python 3.11. Actual dependency
versions and Python version enter provenance. These new estimators report association,
author-asserted assumptions and no established causal effect or uncertainty interval.
Positivity diagnostics, fitted estimands and placebo checks do not prove identification.
Complete unit changes/distributions are descriptive capabilities, not new Recipes.
Panel partitioning is an option of one Method, not a Method per window.

Direct local trials keep computation in the caller process for debugging and do not
promise a hard CPU timeout. Server statistical helpers run after governed extraction
in a terminable child process with bounded data and without provider credentials.
Cancellation/deadline/crash preserves ordinary Run query evidence. Child termination
does not imply warehouse cancellation; in-process jobs and their existing recovery
contract remain unchanged. This is not a sandbox for arbitrary uploaded code.

Complete Journey adds a native Cube panel over its existing eligible campaign-household
materialization and explicitly exposes the observation unit. The panel's physical row
key remains private. Its pre/post dates denote provider-defined 30-day window starts,
not actual campaign receipt or daily purchase outcomes. No database rows or historical
Runs are migrated. Default causal sample scenarios refuse unknown assumptions;
explicit hypothetical design experiments still report association and can refuse poor
observed support. Independent SQL verifies descriptive/window calculations; synthetic
fixtures provide known effects. Neither dataset name nor library use supplies causal
ground truth. No existing local service/data volume is removed.

## 082. Evaluate CEM separately from PyWhy effect estimators

Status: evaluated recommendation; production migration not adopted (2026-10-12).

The review recommends retaining CEM 1.1.1 for compatibility and aggregate-based
matched comparisons, separating its reusable selection/balance/evidence concerns,
and avoiding a universal DoWhy backend. Current target-weighted common-stratum
contrasts are not automatically full-population ATE/ATT; coarsened balance does not
establish original-variable balance. Future interpretation changes require explicit
new contracts rather than rewriting historical Runs or silently repinning Recipes.

The executable lab in examples/methods/pywhy_review compares DoWhy native estimators,
the DoWhy/EconML wrapper and direct EconML on known synthetic effects under DoWhy
0.13/NumPy 1.26.4 and 0.14/NumPy 2.2.6. It exposes wrapper ATT population forwarding
and modifier-selection pitfalls and keeps numerical warnings visible. Typed local
adapters are evaluation-only; categorical/continuous/CATE support is not promoted to
builtins. Existing builtin versions, dependencies and historical evidence are unchanged.
DoWhy 0.14 conflicts with current NumPy constraints; successful point-estimate smoke
tests do not approve the upgrade or inference support.

The paired public guides document assumptions, executed vs proposed APIs, migration
gates, version-resolution limitations, Complete Journey limits and precise product
wording. Neither library use, identification under an assumed graph nor refutation
establishes a real-world causal effect. See guides/pywhy-review.md and
ko/guides/pywhy-review.md for evidence and the proposed staged implementation.

## ADR-083 — Native statistical-library APIs in authored Methods

**Status:** Accepted (2026-10-12). Refines the authoring guidance in ADR-081/082.

Do not require Method contributors to learn a Decision Layer estimator facade over
DoWhy/EconML. They write ordinary native-library calls with explicit estimator,
graph, contrast, target population and optional diagnostics. Existing builtin
`fit_dowhy`/`require_design` helpers are reusable implementation details, not a
mandatory extension API. No new generalized estimator/validator configuration is
introduced by this decision.

Keep `ctx.entities` and `ctx.compute` as governed extraction and execution boundaries.
A developer-owned pure calculation function can also run on a DataFrame outside
Decision Layer. Local notebooks may define it directly; server deployments need a
reviewed importable top-level Python function for the existing child-process contract.
Shared execution retains source authorization, semantic grain/scope, dependency and
resource checks, query evidence and version provenance. Analytical data conditions
and identification assumptions must remain explicit and tested; native library use
and author assertions do not establish causal identification.

The paired hands-on notebooks now show native DoWhy binary regression, standalone
Python calculation and semantic invocation, including refusal before data queries
for undeclared assumptions. This changes contributor examples and guidance, not
existing builtin versions, Recipe pins, historical Runs or estimator behavior.

## ADR-084 — Small Method signatures and compatibility-only analysis designs

**Status:** Accepted (2026-10-12). Refines ADR-081/083 authoring contracts.

New contributors write typed Python functions and pass named arguments directly to
MethodSession.run. Signature-generated roles/parameters remain internal validation
metadata; introductory notebooks no longer require manifest inspection or split
measure/dimension/parameter maps. Semantic references, common scope, authorization,
query limits, package checks and provenance retain their canonical contracts.

Remove AnalysisDesign, assumption checkboxes and configurable seeds from current
statistical authoring examples. A boolean assertion is not identification evidence.
Reviewed binary regression and constant binary LinearDML use four data inputs;
exactly-two-period contrast accepts only meaningful extraction windows/granularity.
Algorithm choices and reproducibility constants belong to reviewed implementation.
Data checks still refuse unsupported inputs; results explicitly record assumptions
as not_verified, remain associational and do not promise causal identification or
uncertainty intervals. No universal estimator configuration or plugin runtime is added.

Register stats.binary_regression, stats.linear_dml and stats.two_period_contrast as
new contracts. Preserve stats.adjusted_difference, stats.dml and stats.did 1.0.0 in
legacy_advanced.py with their original required designs and numerical procedures.
The registry cannot resolve multiple implementations per ID, so new IDs are required
for honest coexistence. No automatic Recipe repinning or historical Run rewriting.
AnalysisDesign parsing stays in the internal compatibility schema; it is removed
from ordinary public authoring exports. Old source imports must move to the explicit
compatibility schema if required; serialized old contracts remain executable.

Native DoWhy/EconML APIs remain available inside developer-owned ordinary Python
calculation functions. require_design is legacy-only; fit_dowhy is not an authoring
facade. Current notebooks, scenario tests and paired English/Korean guides use the
new minimal path. Existing CEM contracts are unaffected by this refactor.

## ADR-085 — Table output for grouped queries and time trends

**Status:** Accepted (2026-10-14). Refines ADR-081's preferred authoring outputs.

New Method functions use `Table` for row-shaped results, including monthly trends,
and `Estimate` for a scalar estimate. `Table.from_dataset` automatically preserves
the provider-returned semantic column references, aliases, roles and bucket
granularity in the additive `Artifact.columns` contract. `Artifact.data` remains
the existing row list, so Python callers do not need a new access path or duplicate
time-axis configuration. Plain `Table(rows)` has no inferred semantic metadata.

Web uses this metadata to render a trend for one bucketed time axis with measures
and no extra grouping/entity columns. Grouped panels remain tables until explicit
series selection is supported; date-looking strings and arbitrary time dimensions
do not imply a trend. This is shared presentation, not an alternative execution
model or a claim about analytical validity. No missing bucket is filled with zero.

Keep the TimeSeries authoring class and existing stored time_series artifacts as
compatibility contracts. Existing builtin Method versions, pinned Recipes, result
capabilities (including time_series), and historical Runs are not rewritten.
The contributor example.series changes its output contract in version 2.0.0;
consumers of the example's 1.0.0 payload must explicitly migrate. New and historical
outputs both render through shared Web helpers. Python, REST and MCP receive the
same canonical rows and column metadata, with validation and provenance intact.

## ADR-086 — Association for observational Method interpretation

**Status:** Accepted (2026-10-14). Refines the preferred interpretation labels.

New Methods use `interpretation="association"` for descriptive summaries and
associational analyses, aligned with the observational first rung of the Causal
Ladder. This label includes aggregates, grouped values, trends and regression
associations; it neither requires a correlation nor establishes a causal effect.
The distinction between summarizing and modeling relationships remains in Method
behavior, documentation and capabilities rather than another developer choice.

Add association to canonical manifests, Results and goals. Keep descriptive and
associational for legacy parsing, execution and stored evidence. Do not rewrite
historical Runs, repin Recipes or relabel installed builtin Method versions. New
contributor examples use association. Web presents all three observational labels
as Association; MCP instructions limit all three to noncausal claims.

New association goals accept association, descriptive and associational results
only when required capabilities and semantic references also match. Conditional
causal results do not silently satisfy these goals. Existing descriptive wildcard
goal behavior and associational exact-match behavior remain compatible; migrate
legacy goals explicitly when adopting the new classification. No Intervention or
Counterfactual class is added here, and causal_conditional is not upgraded by name.

## ADR-087 — Inspect Method candidates without adding an intent taxonomy

Status: accepted (2026-10-14).

Method authoring defaults observational interpretation to `association`; explicit old
labels remain unchanged. Function annotations generate executable inputs/outputs and
a single docstring supplies purpose and limitations. Missing legacy docstrings remain
executable but are flagged during discovery. We do not infer analysis purpose, causal
identification or result capabilities from arbitrary Python or the Table return type.

Keep optional `provides` as exact result assertions consumed by Recipe routing and
completion. Removing it would weaken existing evidence contracts. New function
assertions reject scalar strings, prose, empty/duplicate names; custom names remain
an explicit tested extension, not mandatory discovery tags. The registry itself
supplies the available vocabulary instead of another universal taxonomy. Invalid
package specifiers and ambiguous optional union annotations fail at definition time.

Add read-only MethodSearchRequest and shared discovery used by MethodSession,
POST /methods:search, MCP find_methods and Web Method requirement inspection. Reuse
AnalysisGoal, manifests and the Registry's semantic-role checks. Compare declared
capabilities, interpretation, provider features, installed versions and visible input
types. Return candidates and exclusions, type-compatible references from the goal,
conditional capabilities and remaining required inputs. Do not execute queries, rank
natural-language relevance, select automatically or claim preflight proves joins,
period validity, data sufficiency, authority or analytical assumptions. No outcome
capability is granted by discovery. Execution still revalidates everything.

Remove MCP hardcoded CEM-for-relationships and universal change/drilldown sequences.
These conflict with Method diversity and Recipe-owned procedure (superseding that
part of earlier MCP instructions, not estimator implementations). MCP asks clients to
inspect candidates and clarify ambiguity, preserving existing Recipe review and goal
outcome contracts. Instruction-following is not a guarantee of language-model behavior.

Keep existing kind/execution/editor metadata for compatibility and current consumers;
none is required beyond the existing defaults for simple authored functions. Do not
pretend execution metadata itself isolates computation: ctx.compute owns that boundary.
Protect nonpublic semantic objects at the context boundary as well as discovery.

No Method versions, Recipe pins or historical Run snapshots are rewritten. Discovery
is additive; malformed new declarations need correction. Deterministic tests use
already-resolved goals and measure structural narrowing, not LLM selection accuracy.
Live client comparisons and learned selection remain unimplemented. See the paired
Method discovery guides for the field audit, scenarios and executable examples.


## ADR-088 — Retire duplicate statistical contracts from current choices

Status: accepted (2026-10-14).

Remove stats.adjusted_difference, stats.dml and stats.did from the default Method
catalog and candidate discovery. Their current authoring paths are respectively
stats.binary_regression, stats.linear_dml and stats.two_period_contrast. This is a
catalog retirement, not a declaration that the old and new contracts are identical.
Old required design objects, seeds, diagnostics and version evidence remain intact.

Register those three as compatibility implementations. Registry.get and explicit
execution resolve them for pinned Recipes and existing callers. manifests() returns
only current choices; internal inspection can include compatibility implementations.
REST, MCP, Web and local Python share this registry behavior. No frontend name filter,
new authoring configuration or silent alias is introduced. Historical Run snapshots
are unchanged. Tests continue to execute the old panel contract and verify version
and design input retention, while checking its exclusion from candidate lists.

Keep OLS, binary regression adjustment, LinearDML, panel contrasts and CEM because
they answer different analytical questions with different assumptions and data needs.
Keep unit-change and unit-distribution Methods for complete-unit extraction and cohort
checks that ordinary aggregate queries do not replace. Current public catalog: 11
Methods; the executable discovery lab adds one authored example, so it lists 12.


## ADR-089 — CEM is compatibility-only in the default catalog

Status: accepted (2026-10-14). Refines ADR-082/088.

Exclude causal.cem from default manifests and Method candidate discovery. Keep its
original 1.1.1 implementation for explicit existing Recipe references and execution.
This is an interim support decision, not equivalence to regression adjustment or DML,
and not deletion of historical evidence. The shared registry applies the exclusion
across Python, REST, MCP and Web. Current public catalog contains 10 Methods.


## ADR-090 — Three default MVP Methods; ordinary Python extensions

Status: accepted (2026-10-14). Supersedes the default catalog scope of ADR-088/089.

Default discovery offers only query.aggregate, query.trend and query.drilldown.
They cover governed lookup, period comparison and iterative branch investigation,
the initial organizational procedure in PRODUCT_CONTEXT. Aggregate does not replace
trend/drilldown validation, decomposition, selection contracts or comparison tests.

Peer comparison, unit change/distribution, OLS, binary regression, LinearDML and
panel contrasts are optional implementations outside default suggestions. Existing
explicit Recipes still resolve their original contracts through compatibility
registration. CEM and the three prior design-object contracts remain legacy-only.
Stored evidence and original versions are not rewritten.

Use the existing reviewed Python registry to enable an optional implementation:
registry.register(PeerComparison()) or registry.register(ols) makes it discoverable.
Local sessions acknowledge an existing compatibility implementation with replace=True.
Dependencies remain explicit installed extras and execution checks remain unchanged.
No plugin manifest, dynamic installer, marketplace, downloaded execution or separate
frontend runtime is introduced. This is an extension path, not an Obsidian-style
interactive plugin product. Requests requiring an unlisted capability receive no
Method candidate unless a reviewed extension or existing suitable Recipe provides it.

The canonical registry controls Web, REST, MCP and Python lists. All implementations
remain resolvable to preserve previously authored tests and fixed Recipes; default
visibility is deliberately distinct from permission to run an explicit contract.
A future hard support-removal policy would require a separate migration decision.


## ADR-091 — Two small DoWhy analyses alongside the three core queries

Status: accepted (2026-10-14). Refines ADR-090 at the user's request.

Expose stats.binary_matching 1.0.0 and the existing stats.binary_regression 1.0.0
alongside aggregate, trend and drilldown. Do not add a configurable universal causal
estimator. Both take outcome, binary treatment, pre-treatment confounders and unit;
semantic definitions, joins, extraction bounds and permissions remain provider-owned.

Matching calls native DoWhy 0.13 backdoor.distance_matching: standardized one-hot
covariates, one nearest control per treated unit, with replacement, target ATT (1 vs 0).
Use the native matched indices to inspect the actual match. Require >=30 units per
arm, fitted propensity within [0.05,0.95], >=30 unique matched controls, maximum
standardized Euclidean distance <=1 and maximum absolute post-match SMD <=0.1.
These are versioned diagnostic policies, not overlap or identification proofs.
Refuse unsupported data rather than trim the treated target silently. Reject missing,
nonfinite, duplicate units and constant/no-variation covariates. Matrix bounds and
server computation deadlines apply. No default bootstrap CI for reused matching units.

Regression uses the existing native DoWhy linear-regression contrast (ATE 0 vs 1),
full-rank/data/support checks and placebo diagnostic. Its installed version and
numerical contract are unchanged. Label it as DoWhy OLS regression adjustment;
ordinary stats.ols coefficients remain an optional distinct analysis.

The graph assumes measured covariates precede treatment and block common causes.
Temporal ordering, no unmeasured confounding, independent units and no interference
are unverified domain assumptions. Results stay association/associational and state
causal_claim=not_established and uncertainty=not_reported. Refutation and balanced
observed covariates are not proof of causality. No AnalysisDesign checkbox is added.

Synthetic known effects and unsupported inputs are exercised in pytest and an ordinary
Python example using the same entity-query MethodSession pipeline. No live-data
causal ground truth is asserted. Complete Journey Docker includes the reviewed stats
and dowhy extras so the displayed Methods can execute; no automatic runtime installs.
Use documented DoWhy 0.13, NumPy <2 and scikit-learn <1.7, without silently adopting
0.14. Keep existing optional/compatibility Methods and historical evidence intact.


## ADR-092 — Numeric-treatment OLS defaults to the stored-unit slope

Status: accepted (2026-10-14). Refines ADR-091.

Replace binary_regression in the five-item default catalog with
stats.regression_adjustment 1.0.0. Preserve stats.binary_regression 1.0.0 as an
explicit compatibility implementation; no Recipe alias or historical rewrite.
Matching stays binary. Regression accepts treatment as a numeric Dimension or
Measure, plus outcome, pre-treatment confounders and unit. Both comparison values
are optional; omit both to return the constant adjusted change per stored treatment
unit. Specify both to return a signed contrast. Binary contrasts compare only 0/1.
Categorical coding is not inferred, nor are numeric treatments coarsened.

Call native DoWhy 0.13 backdoor.linear_regression under an assumed additive DAG.
For the default slope, fit an in-range contrast using observed min/max and normalize
by its width. Do not simulate a +1 intervention outside a narrow observed range.
Record result_scale, slope, estimation_contrast, semantic treatment reference,
observed range and original stored scale. Percentages are not automatically converted.

Require unique complete finite units, varying encoded confounders, full-rank
predictors and residual degrees of freedom. Binary input retains the observed
propensity diagnostic and >=30 units per arm. Continuous input requires >=60 units
and >=10 distinct values. Explicit contrasts must be finite, different and inside
the observed range; omission of one contrast endpoint refuses before querying data.
Range inclusion does not verify joint dose/covariate overlap, which remains unverified.
Constant linear slope, temporal order and causal identification assumptions remain
explicit limitations. Results stay association with no uncertainty interval or
established causal claim. No new AnalysisDesign, estimator facade or treatment bins.

Tests use known slopes, binary data, percentage rescaling, explicit contrasts and
refusal scenarios. Paired workshop notebooks run the same implementation through a
semantic fixture session. Server Docker includes the existing reviewed DoWhy stack.

## ADR-093 — A small executable sample and client setup entry point

Status: accepted (2026-10-14), following the request for a one-command first-use experience.

Ship a separate synthetic Cube/PostgreSQL sample with isolated Compose resources.
The walkthrough records an analysis through REST, promotes it with the existing
Run-to-Recipe API and replays it on a new period. A tied leader requests input.
It adds no Method, provider, semantic definition inside a Recipe or execution engine.

A thin Node installer starts and checks this sample, then registers the existing
stdio MCP adapter with Claude Code. The adapter runs inside the API container;
users need no separate Python installation or handwritten MCP JSON. The bridge
starts stopped API dependencies and sends startup output to stderr, preserving
stdio protocol output. Setup does not overwrite an unrelated client registration.
Web is an optional inspection surface after setup, not required for questions.
The example requires running Docker; it is not a zero-dependency installation.

The deterministic walkthrough is not a model benchmark or multi-user authorization
proof. Explicit Run registration remains required; no chat interception, automatic
Recipe publication or generated analytical code execution is introduced. Real
organization sources still require their own connection and authorization.

The installer retains runtime files in `~/.local/share/decision-layer/runtime`
(overridable by `DL_INSTALL_DIR`) so a client registration does not depend on an
npm cache entry. It refuses unmanaged installation directories and preserves sample
state in Docker volumes. GitHub-package installation is a distribution path, not a
new plugin runtime or automatic publication mechanism.

## ADR-094 — Fail closed administration and explicit procedure publication

Status: accepted (2026-10-15), first implementation increment of the revised PRD.
Supersedes ADR-033's missing-key administration, ADR-038's unrestricted Recipe
writes, ADR-050/061's immediate publication, and ADR-051's physical Recipe deletion.
The immutable version and draft rules of ADR-043 remain.

Only explicit `local` and `demo` deployment modes are supported. `shared` and
unknown modes fail at application construction. This is a release gate, not a
claim that setting a mode secures a publicly exposed server. Bind local services
to loopback; the Compose ports do so. HTTP Host/Origin checks reject unapproved
browser origins and DNS-rebinding hostnames. Local service credentials remain an
explicit opt-in, default false in the general environment example; the isolated
synthetic sample opts in. Provider-authenticated subjects are still local trust
identities. Independent verified application identity, DNS/egress enforcement,
source credential/user separation and a real Python sandbox remain required before
shared deployment. No old Run owner is reassigned.

Missing `DL_SOURCE_ADMIN_TOKEN` now disables HTTP source save/test. A supplied
admin key must also respect exact operator-approved endpoints: the configured
Cube/dbt URL or `DL_SOURCE_ALLOWED_URLS`. Saved legacy endpoints outside that set
fail closed until an operator approves/configures them. A changed endpoint cannot
inherit the previous encrypted secret; a connection test cannot sign with the old
secret for a different endpoint. Environment credentials belong to the environment
endpoint. This closes arbitrary URL selection by HTTP callers; it does not claim
DNS pinning or constrain trusted local Python connections.

`DL_RECIPE_EDITORS` and `DL_RECIPE_PUBLISHERS` list authenticated subjects. Publishers
may edit; readers cannot write or inspect drafts. Explicit local service identity
is the runtime owner's identity, not an arbitrary token with a similar subject.
Run-to-Recipe candidate/save requires Run ownership and editing permission; shared
read access never grants promotion. Default save creates a draft. Publication
requires publisher permission and either the existing draft publication endpoint
or an explicitly supplied reviewed Recipe. Questions and Run-specific purposes
are omitted from generated drafts. Fixed values, filters and origin references
still require review; no automatic sensitive-data detection is claimed.

Recipe DELETE now writes a retirement marker in `.retired/`, retaining every YAML
version. It removes the asset from discovery/execution; publisher-only restore
checks the archived base version. New save/publish/archive/restore operations write
actor/version/time events in `.history/`. These filesystem records are auditable
local history, not a tamper-proof transactional audit service. Git changes remain
operator-owned. Existing published assets are not retrospectively approved or
redacted, and historical Run snapshots remain unchanged.

REST, Web and MCP share these routes. `save_procedure` returns a draft;
`publish_procedure` publishes a reviewed draft. Existing clients relying on immediate
publication must add review/publication. The synthetic replay follows this flow.
The installer supports `--client codex` alongside Claude, preserves conflicting
registrations and uses the same existing stdio bridge (extends ADR-093).

## ADR-095 — Native calculations adapt to existing Method contracts

Status: accepted (2026-10-15), extends ADR-081/083/084 without replacing typed Methods.

`calculation(fn, name=..., version=..., table=InputTable(...))` creates a normal
Method for an existing synchronous Python function. The function's first argument
receives records or a pandas DataFrame; remaining named scalar options use the
existing parameter contract. Column aliases map to runtime semantic roles; no
metric SQL or business definitions move into the calculation. Default output is
Table; Estimate and explicit output adapters are supported. Executable validators
return ValidationResult records. The default interpretation is association.

Extraction uses the existing context aggregate/entity paths, scoped credentials,
provider capabilities and budgets. Missing/non-finite required values, insufficient
rows and duplicate returned grain stop before the native calculation. Source
completeness, official meaning and causal assumptions are not verified by these
checks. The registered Method version, queries, input mapping and native function
name accompany the result. Existing async/class Methods keep their contracts;
multiple queries, time bucketing and more complex inputs remain advanced Methods.

Local trials retain ordinary breakpoints. Server execution uses the existing
bounded worker and importable module-level functions; context/credentials are not
calculation arguments. This worker is not an arbitrary-code security sandbox.
Reviewed package registration remains required; no code upload or local data-file
source is added. The paired workshop notebooks start with the tested native path,
retain advanced examples and show existing Cube/dbt connections with explicit
skipped live checks. dbt entity extraction and direct DW/DM/BigQuery remain unsupported.


## ADR-096 — Initial product supports Cube only

Status: accepted (2026-10-15), narrows ADR-073's product provider coverage and
ADR-095's live notebook examples. Supersedes the PRD's direct-connection P0 proposal.

The initial journey is Claude/Codex → example Cube → organization Cube → save and
rerun a procedure. Do not implement dbt, BigQuery, direct DW/DM or local data-file
connections for this increment. Cube may itself use a warehouse or mart; this is
not a direct Decision Layer connector. Organizations without Cube can evaluate the
sample but cannot use their own data in this release. This limits the initial
market deliberately to test reuse before expanding backend coverage.

Source input schemas, the configured provider factory, provider discovery and Web
settings offer Cube only. Unsupported stored providers fail closed with an explicit
message, never silently switch to Cube. To recover a deployment with an old active
provider, an operator explicitly sets DL_SOURCE_PROVIDER=cube and CUBE_API_URL to an
approved Cube endpoint before restart, or uses SourceConfigManager.save with an
explicit Cube configuration offline. Prior connection records remain stored.

The existing dbt module and isolated adapter contract tests are retained as legacy
reference, not wired into product connection configuration. The generic provider
protocol and dependency injection remain for tests and future integrations; this
is not a sandbox that prevents trusted Python code from importing old modules.
Run snapshots, owner identities and semantic URIs are not rewritten. Old dbt Recipes
cannot be rerun against Cube by renaming refs; reviewed bindings and numerical
comparison must produce a new version. Historical records remain in storage; access
still requires the original ownership rules and credentials, not automatic identity
migration. Operators needing the former execution behavior must retain a pinned
legacy runtime, separate from this initial product configuration.

The paired Method notebooks show ordinary calculations plus Cube only. Existing
advanced Methods remain valid. Raw SQL/DDL/DML/DCL and Cube management/refresh
operations are not exposed. Cube's own SQL, upstream privileges and pre-aggregation
writes cannot be certified solely by a read API call. Dedicated source permissions
and Cube deployment review remain necessary. Direct SQL AST and backend-specific
security tests are deferred with their connectors, not claimed as implemented.

Revisit one additional backend only after Cube reuse is demonstrated and repeated
customer demand identifies a specific blocked workflow. Preserve generic contracts
without prebuilding adapters. Shared deployment remains disabled under ADR-094.

## ADR-097 — Method assets with advisory Skills and ordinary Python

Status: accepted (2026-10-15), revises ADR-003's executable-only Method definition
and extends ADR-095. Explicitly requested as a runtime/authoring change, not merely
a notebook rewrite. Cube-only scope and local/demo security gates remain.

A discoverable Method asset has an implementation discriminator. `python` remains
an executable capability; `skill` is versioned advisory Markdown with suggested
registered tools. Both appear in the method catalog, but only Python can execute
as a Run/Recipe step. `describe_method` includes Skill text on demand;
`get_method_guide(authoring|cube-query)` provides package-version-matched guidance.
The Cube guide covers discovery, meaning, grain, aggregation, periods, peers,
refusals and read-only boundaries. Cube models are not Wren MDL. Skill text is
never counted as evidence, validation, permission or automatic goal coverage.

`start_analysis(guide=name)` / RunStartRequest records the selected Skill's exact
text/version/hash on the Run. The AI executes ordinary registered tools on that
Run; the engine does not interpret Markdown or automatically replay its steps.
A Recipe is required for deterministic sequence/branch enforcement. Skills may
recommend advanced/compatibility tools through explicit lookup; this does not
re-enable them all in default discovery. Agent adherence remains an evaluation
question, not an engine guarantee. MCP allow-lists still apply to execution.

`python_method(fn, inputs={argument: DataInput(...)})` adapts an ordinary synchronous
function. No `ctx`, async, semantic annotations or output subclasses are required
inside it. Columns use one name for both the function and runtime semantic binding;
multiple input tables, explicit comparison periods and time buckets are supported.
Simple options infer types from defaults/annotations or explicit parameter types.
Numbers, dictionaries, row lists and DataFrames adapt to normal Result artifacts;
complex library outputs may use a reviewed output adapter. Advanced async/class
Methods and the earlier `calculation` adapter remain compatible.

Data extraction uses the existing scoped context/provider/budgets. Python input
checks actually execute: minimum rows, columns, finite measures and unique non-null
returned grain. Additional ordinary checks run before the calculation; failures
stop it and are recorded. The adapter never asserts causal validity. Library-internal
checks are not individually marked as validated unless explicitly instrumented.
Source/function/check/adapter fingerprints and installed dependency versions improve
inspection, but do not trace arbitrary Python internals, closures, network/filesystem
access or recreate the full environment. The existing bounded worker is not a
sandbox. No remote code-upload or shared arbitrary-code execution is added.

Operators own Python modules exporting `METHODS` and Skill Markdown directories in
Git. `DL_METHOD_MODULES` imports reviewed installed modules; `DL_SKILLS_DIR` loads
reviewed Markdown. All Markdown in that directory must be assets. Startup rejects
duplicate names and invalid tool references. Each API app has an isolated registry
used by discovery, execution, Recipe validation/configuration/routing/promotion.
There is no Method editing/publication UI: trial, tests, Git review, version bump,
package/environment pinning and restart are the current publishing flow. Retain
released packages to reproduce old code; snapshots alone do not archive binaries.

Old manifests default to Python, old Runs default to no Skill snapshots. Historical
Run data is not rewritten. Changed code requires a new Method version; pinned
Recipe steps reject an installed version mismatch. Run-to-Recipe promotion accepts
native measure aliases instead of requiring a parameter literally named `metric`.
The main ko/en notebooks now teach these paths; former advanced content is retained
as `advanced_method.*.ipynb`. No database schema migration is required for the additive
JSON fields. Old clients must filter Skill assets from executable choices.

## ADR-098 — Agent-executed Skill steps inside mixed Recipes

Status: accepted (2026-10-15), supersedes ADR-097's restriction that all Skills are
Run-level guidance only. The user explicitly requires query-oriented Skills and
Python computations to connect as Method steps, visible in the same Run.

Skill Markdown may opt into `query_execution: true` with existing typed role and
parameter definitions. `analysis.drilldown` and `analysis.peer_comparison` are new
Skill implementations. They contain analytical instructions, not hidden calls to
the former Python drilldown/peer classes. The common engine executes structured
Cube read queries proposed by the client agent. `query.drilldown` and
`query.peer_comparison` retain their exact implementations and versions for old
Recipes; drilldown leaves default discovery. Existing advisory-only Skills remain
readable but cannot become executable stages. No old ID silently changes behavior.

A mixed pipeline pauses at a Skill with `AGENT_EXECUTION_REQUIRED`. The client uses
`run_skill_query` and `finish_skill_step`; completion resumes the next Skill or
Python stage. Web-only execution waits for a client agent, never pretends to run
Markdown. Execution/adherence are distinct: prose is advisory; bound metrics, query
period, required filters, budgets, source permissions and evidence references are
checked by code. The Skill snapshot includes its manifest, text, version and hash.
Per-query IDs, purposes, structured specs, real Results, errors, timestamps and
caller-reported/protocol agent attribution are persisted under the Skill step.

Skill queries use aggregate DatasetSpecs, explicit dates and bounded rows. Current
periods must equal Run scope; comparison periods must be explicitly bound to the
Skill. Only bound metrics and their provider-declared counts are allowed. Inherited
population and arbitrary required filters cannot be omitted. Source discovery and
provider checks remain canonical. No raw SQL, source administration, arbitrary
Python or new data provider is exposed. Client-generated narrative is not numeric
evidence or validation. Query success does not certify peer suitability or complete
coverage. The Skill currently certifies no analytical `provides` capabilities.

A selected group must point to a real query ID/row/dimension. It is explicitly
`selected_group`, not a server-verified ranking/anomaly. Exports retain the selected
value and its evidence, reason and full query filters. Equality-only path/condition
projections remain useful for subjects; full population propagation uses
`selected_group.evidence.filters`, including exclusions and ranges. Native Python
DataInput supports a separate `filters_parameter` so a later calculation consumes
those filters without adding SDK conventions to its function body. Fixed Python
steps remain deterministic; agent decisions may differ on replay and are recorded.

An active Skill blocks unrelated steps and Run completion. Query IDs deduplicate
identical requests; a changed request with the same ID is rejected. Failed queries
remain visible; corrected queries require new IDs. Bounded workers and query
budgets still apply. Pending agent stages survive restart; interrupted reads are
marked interrupted and not silently replayed. Shared viewers cannot execute or
finish stages. Historical Runs remain unchanged; additive JSON fields need no SQL
migration. Reviewed legacy Recipes require an explicit new version to adopt Skills.

The complete-journey demo mounts a reviewed example Python module read-only and
registers its ordinary statsmodels function to demonstrate the full chain. This is
a demo asset, not another builtin estimator or a code-upload feature. Python remains
trusted installed code; shared arbitrary-code hosting remains disabled.

### ADR-098 follow-up — bounded MCP evidence after real Claude trials

Real Claude MCP trials reached successful server-side Skill→Skill→Python execution,
but repeated full Skill query logs caused 54–92 KB tool replies. Claude persisted or
rejected these oversized replies and could not inspect the final coefficient table.
A completed server Run alone therefore did not establish usable client execution.

MCP Run responses now include the active frozen guide once, completed Skill guide
metadata and query summaries. They do not duplicate every stored table or native SQL.
`run_skill_query` returns up to 25 rows; `get_skill_query` reads a stored query page
through the same authorized Run read path, without executing another provider query.
Pagination reports total rows, next offset and absolute row-index semantics for
selection. Validation, errors, provenance summaries and exported filters remain
visible. Full Run evidence and Web inspection are unchanged; compaction uses copies.
This is an interface payload fix, not a new analytical or permission model.

## ADR-099 — Korean query Skills and separate time calculations

Status: accepted (2026-10-16). The user approved replacing the public aggregate/trend
Method entries with Skills and explicitly requested Korean Skill authoring.

Default discovery now offers analysis.metric_lookup and analysis.trend as Korean
query-executing Markdown. query.aggregate/query.trend remain their original Python
implementations and versions for explicit existing Recipes; historical Run evidence
is unchanged. No Skill receives a provides capability merely by following prose.
The existing shared Skill query runtime handles structured Cube reads and logging.

Time calculations and executable validators remain code: stats.period_change calls
the shared period-change calculation for explicit dates, supported tests, per-day
comparisons and source-declared factors, with period/observed-coverage checks.
stats.series_diagnostics computes largest observed adjacent moves with ties retained
and runs calendar/observed-coverage checks. Both consume full explicit population
filters. Neither delegates to legacy Trend nor certifies ingestion completeness or
causal validity. Missing period values stop the new comparison. No generic pipeline
or validator execution language is introduced.

All shipped Skill assets are Korean. Existing drilldown/peer and advisory guides
release as 1.0.1 with new hashes; old Run snapshots retain the original English text.
The example campaign Recipe becomes 1.0.1 with explicit Skill pins. Existing pinned
1.0.0 Skill Recipes require explicit review and a new Recipe version; an installed
version mismatch is rejected rather than silently substituted. This registry still
loads one version per logical Method ID; retain the old package/environment for
exact old-version reruns. Legacy query.aggregate/query.trend Recipes need no rewrite.

## ADR-100 — Inspectable code and opt-in local Method/Skill editing

Status: accepted (2026-10-16). The user explicitly requested Python source visibility,
UI editing of both Python and Skills, and a readable/high-contrast Skill display.
This supersedes ADR-097's no-Method-editing-UI/no-HTTP-code-publication boundary for
trusted local/demo operators. Runtime AI still maps to registered assets; no arbitrary
Python/SQL execution tool or untrusted shared code host is added.

Method detail renders Skill Markdown safely (no raw HTML or automatic image fetch),
and syntax-highlights Python entry/helper code. New Run records retain selected Python
source/hash/version; old Runs are not backfilled from current code. The snapshot covers
entry modules and selected local helpers only, not full library internals or environments.

UI editing uses a separate managed asset directory with draft revision/base-version
CAS, explicit version increments, source comparison, syntax/registration checking and
reviewed immutable publication. Installed Git/package files are never edited in place.
Git remains the authority for installed versions, managed files for UI releases; moving
changes between them is an explicit operator action. Concurrent/stale writes are rejected.

Python code must export one registered Method in METHODS under the same logical name.
The managed publication version is applied as registration metadata by visible generated
code. Checking imports executes code in a credential-reduced child with a 15-second
limit, while publication imports trusted reviewed code in the server. This does not
isolate host files/network or certify calculations. UI labels the limited check scope
and requires review before Python checks and all publication. Draft save alone does not
execute code or change active assets. No dependency installation is performed by the UI.

DL_ALLOW_METHOD_EDITING plus DL_METHOD_ASSETS_DIR opt in. Separate Method editor and
publisher roles prevent Recipe publishers from acquiring code-execution rights. The
explicit local service operator may edit in local/demo; shared mode remains blocked.
The sample demo enables editing, generic Compose leaves it off. No anonymous shared
code publication is claimed safe. Source inspection uses registered assets only; there
is no caller-supplied filesystem path or module import endpoint.

The registry stores exact installed/managed versions and retains old releases across
publication/restart. Pinned Recipe validation/execution resolves that version, and
unavailable pins in new authoring/execution are rejected rather than silently substituted.
Historical files with unavailable versions remain structurally readable so retained
old Recipe versions cannot prevent startup; execution has no fallback. Startup package changes
still require compatible dependencies/source environments; source snapshots do not
recreate all binaries. An installed/UI same-version collision blocks startup pending explicit source/version
reconciliation. Higher installed versions remain current while older managed versions
remain resolvable. Local draft/publish locking is single-process, not distributed.

## ADR-101 — Authorable code is distinct from complete execution source

Status: accepted (2026-10-16). The user rejected platform internals as the primary
Method authoring experience. Code visibility alone is insufficient when the first
screen/editor contains unrelated assets, Recipe builders and framework contracts.

The normal extension remains an ordinary synchronous Python function plus separate
`python_method`/`DataInput` registration. No new mandatory Method base class,
async function, Artifact or bespoke estimator API is introduced for contributors.

Method detail and draft initialization now use the selected asset's functions,
referenced checks/constants/imports and registration, preserving their formatting.
This is an authoring projection, not the exact original file bytes: relative imports
become absolute and UI-managed version metadata is reflected in the registration.
Unknown dynamic module initialization falls back to the full source rather than
pretending to infer its dependencies. Exact entry/helper source and hashes remain
available separately, collapsed by default. Run snapshots retain their own projection
and complete evidence; current code never replaces missing historical evidence.

`stats.series_diagnostics@1.1.0` is an actual calculation split, not an illustrative
copy: a normal pandas function accepts period/metric/value rows and returns the
largest adjacent changes with ties. Its existing source-bound adapter retains Cube
queries, scope/filter propagation, checks, warnings and output contracts. Editing
that function changes the calculation run by the canonical engine. Its registration
reuses that particular input/output adapter; it is not required boilerplate for new
analyses, which use the general Python registration path. Builtin 1.0.0 remains
installed for pinned Recipes. Other advanced source-aware Methods are not falsely
presented as already migrated to DataInput.

Analytical complexity is not removed by hiding checks or shortening a causal fit.
Required analytical diagnostics remain executable and inspectable. Full source
view and trusted code review/publication rules from ADR-100 remain in force.

ADR-100/101 UX refinement (2026-10-16): the read surface switches in place to a
Python/Markdown editor above the content, with preview/comparison, explicit dirty/
saved/checked/published states, keyboard draft save and unsaved link/unload protection.
Check saves the exact current draft first. Background metadata refreshes do not reset
an editing buffer; save responses do not mark subsequently typed edits as saved.
Conflicts retain local text and offer an explicit remote comparison/rebase. Existing
server revisions, reviewed-code gates, publisher permissions and immutable publication
remain authoritative; this does not add execution APIs or anonymous editing rights.

## ADR-102 — One ordinary calculation entry, explicit input contracts and retained advanced cases

Status: accepted (2026-10-16), requested as an actual registration/runtime change.
Extends ADR-097/101; Cube-only and trusted local publication boundaries remain.

New calculations use `python_method(fn, inputs={argument: DataInput(...)})`. A normal
function receives DataFrame(s)/records and calculation options. It does not select
Cube credentials, semantic objects, query periods or filters. Use one file shape:
imports, ordinary calculation, optional checks/output presentation, METHODS export.
The earlier `calculation/InputTable` remains a frozen compatibility API; it is no
longer a second tutorial path. Advanced async/class contracts are still supported.

DataInput is now a canonical typed model exposed as `MethodManifest.data_inputs`.
The same declarations build the executable roles and appear in REST/MCP/Web.
Simple measures/dimensions remain lists of stable calculation column names. An
entity input may optionally use existing RoleSpec declarations for mixed or
multiple variables; a multiple role expands to name_0, name_1, etc. The source
owns entity identity, metric definitions and aggregation. The engine checks roles,
period/access/budgets, column bounds, actual returned columns, finite measures and
unique non-null returned grain. Resolved alias-to-reference mappings are recorded
as python.resolved_inputs along with existing query specs/native queries. DataFrame
attrs optionally expose semantic_refs for result labels, not credentials or source
control. Missing required bindings refuse before querying; ambiguous time dimensions
use existing NeedsInput. Business-variable roles are not inferred or certified by
these type checks; the client must ask about ambiguous meaning.

stats.binary_matching and stats.regression_adjustment 1.1.0 use actual ordinary
analyze(data, ...) functions and this general input path. DoWhy calls and analytical
diagnostics remain visible. Regression options have an executable pre-query check
in the same bounded compute worker. Presentation records passed diagnostics only
after successful calculation; identification remains unverified. Both installed
1.0.0 implementations and their import paths remain resolvable for pinned Recipes.
Changed input validation and extra provenance justify a new version even where
numerical payloads agree. No historical Run/code snapshot is rewritten.

Two justified advanced cases remain explicit: series_diagnostics 1.1.0 already
has an ordinary pandas function but retains the source-bound adapter for calendar/
observed-coverage checks and its existing time-series/table output contract;
period_change needs provider-declared denominators, aggregation kind and factor
relationships to choose additional queries and valid comparisons. Neither adapter
is a required beginner template. Forcing them into a generic dataframe schema or
removing checks to shorten code would lose their contract; no new loader/DSL is
introduced for cosmetic uniformity.

Default Python choices remain the four distinct numerical capabilities. Central
compatibility registration keeps old aggregate/trend/drilldown/peer, CEM, earlier
statistical contracts and optional unit/panel analyses outside new discovery.
The local pre-change inventory contains 22 Runs including 8 legacy drilldown,
1 trend and 2 aggregate steps. Removing those implementations would break actual
retained assets. No blanket filesystem deletion is justified by absence from the
current UI; public callers can pin previously shipped packages. Repository examples
and managed versions remain usable. Existing UI drafts are preserved and version
conflicts use the existing explicit review path. See the dated evidence directory
for the audit, execution comparisons and remaining limits.

ADR-102 execution follow-up: a real Cube comparison exposed that worker-captured
library warnings were only attached to dict payloads, disappearing for ordinary
function MethodOutput adapters. The common worker now appends those warnings to
Result.warnings. Legacy dict payloads retain backend_warnings for compatibility;
comparisons check numerical payloads and warning preservation separately.

## ADR-103 — Retire redundant default calculations, retain pinned execution (2026-10-16)

**Accepted.** User explicitly removed `stats.period_change`, `stats.series_diagnostics`,
and `example.household_regression` from the product's default choices. Supersedes
their default-catalog status in ADR-099/102; ordinary Python authoring is unchanged.

- Keep released implementations/version lookups for existing Recipes and Runs. The
  default REST/MCP/Python discovery catalog excludes these names. Exact historical
  execution remains supported; this is retirement, not deletion of historical code.
- Operator modules may export `COMPATIBILITY_METHODS` alongside `METHODS`. Managed
  asset restoration/publication preserves a name's compatibility status, so a saved
  UI revision cannot accidentally restore a retired catalog choice on restart. An
  explicit operator registration can still reactivate a Method.
- Publish drilldown/trend instructions as 1.1.0 without referrals to retired methods;
  archive previous released text for exact-version lookup. Skills describe queried
  values and stop unsupported calculation claims. No prose or AI arithmetic replaces
  numerical validation. Existing Run snapshots and managed drafts are not rewritten.
- `campaign_recipe()` 1.1.0 has two query Skills. `legacy_campaign_recipe()` and
  historical evaluation scripts retain the old three-stage procedure explicitly.
  Existing stored Recipe releases are preserved; a new version is required to adopt
  the query-only procedure. Default Python choices remain regression adjustment and
  binary matching.

## ADR-104 — Shared Python formatting and line review (2026-10-16)

**Accepted.** Python Method authors use a pinned Ruff 0.12.3 formatter with one
bundled `methods/python-style.toml` configuration (88 columns, four spaces, double
quotes, stable mode). Root tooling extends that same configuration. No new Method
class or calculation signature is introduced. Prefer imports → calculation →
optional checks/presentation → METHODS; omit unused sections. Statistical imports
may remain local to keep optional dependencies optional at discovery time.

- Current builtin calculation modules, first-method/plain-function examples and
  paired authoring notebooks use the style. The formatter changes layout; function
  options, algorithms and existing version references are unchanged. `make
  format-methods` applies it; `make check-method-format` and CI enforce the scoped
  contributor surface without rewriting frozen compatibility modules.
- New source capture formats only the selected authoring projection, preserving
  comments and referenced definitions. Full evidence files and hashes remain exact,
  and stored Run snapshots/published assets are not rewritten. Thus a readable
  projection can differ in whitespace from the actual source evidence.
- POST `/methods/{name}/source:format` requires enabled editing and Method edit
  permission. It accepts bounded Python text, parses/formats without importing it,
  limits formatter runtime, and compares the before/after AST. It returns text only,
  with no persistence or registration. Syntax errors leave the editor unchanged.
  It does not require trusting/executing a Python draft.
- Web offers explicit formatting, Shift+Alt+F and a one-action revert. Formatting
  changes reset review/check readiness. Save, registration check and publication
  remain explicit. Code/Skill comparison shows actual added/deleted lines with
  original/new line numbers and context; whitespace is not ignored because Python
  indentation is meaningful. Comparisons are bounded and fall back on full preview
  when too large. Formatting/diff never imply analytical validation.

## ADR-105 — Ordinary column arguments and an executable authoring workshop (2026-10-16)

**Accepted.** The authoring unit remains an ordinary synchronous function plus a
small separate `python_method` registration. Extend ADR-097/102 with
`DataInput.column_args`, rather than another decorator, planner or estimator API.
A data scientist can keep `ols(data, outcome, treatment, confounders)` and call it
with their own DataFrame/column names before registering it.

- Function identity/version, row grain, semantic variable roles and materialization
  checks are explicit. Scalar option defaults/types and the function docstring are
  inferred as before. Definitions, joins and source access remain provider-owned.
  Actual refs, scope and filters are supplied per invocation, never inferred from
  parameter spelling. The AI may propose existing catalog objects and ask about
  ambiguous meaning; type checks do not certify confounder choice or causality.
- Each column argument must name a role in its own input and an actual separate
  function parameter. Exactly one input owns each argument. Scalar roles supply a
  column-name string; multiple roles supply ordered lists of resolved aliases.
  Absent optional roles supply None/[]; required omissions refuse before querying.
  These are binding roles, not user-overridable calculation options. Fixed-column
  functions and all installed/pinned Methods remain supported without migration.
- The existing Registry → context → bounded compute path queries, validates and
  injects those names. The manifest serializes the declaration to REST/MCP/Web;
  `python.resolved_inputs` records actual argument and alias-to-ref maps. No AI code
  generation, local-file data connector or separate execution service is added.
- The paired first-Method notebooks now demonstrate direct ordinary Python, governed
  execution, pre-query failures, data refusals, native statsmodels OLS, multiple
  inputs, default DoWhy OLS/matching, module installation and Web/MCP usage. The
  optional column_arguments module is a teaching asset, not a third default Method.
  Offline fixtures and request replay are explicitly distinct from live Cube/AI
  validation. Real Cube execution remains opt-in with discovered references.
- Web explains column arguments and links to the existing single-step Recipe preview.
  Users can choose data/dates and inspect results/queries without saving a Recipe.
  Method deep links seed only declared roles and pin the selected version; they
  must not inject an undeclared metric role into outcome/value-based functions.
  Registration checks do not count as numerical tests. Preview executes published
  code, never an unsaved editor draft. Existing source/version publication boundaries
  remain unchanged.

Validation compares direct/registered numerical results with known synthetic slopes,
checks optional/list arguments and invalid registration, prevents client overrides
and queries on missing bindings, exercises MCP through HTTP and the server worker,
and runs the workshop top to bottom. Analytical correctness still needs Method-
specific tests and independent review of observational assumptions.

## ADR-106 — One Method project from authoring to server registration (2026-10-19)

**Accepted.** The public extension entry is a project identified by
`decision-layer.yaml` (`config_version: 1`, `name: <python_package>`). Definitions live in
`<name>/methods/<definition>/`. A Python entry is `method.py` exporting one `METHOD`
object; a Skill entry is `SKILL.md` using the existing frontmatter contract. Helper
files are not discovered. Ordinary functions and `python_method` / DataInput remain
unchanged; the project adds organization and loading, not another calculation DSL.

- `decision-layer init`, `new python|skill`, `check`, `list`, and `serve` scaffold and
  inspect the same definitions. Lists show source paths. Check validates registration
  and references, never analytical quality. A marked project is found from cwd and
  parents; `--project` / `DL_PROJECT_DIR` explicitly selects it elsewhere. An invalid
  explicit project fails rather than silently serving only built-ins.
- API startup, CLI and MethodSession.load_project share the project loader and
  canonical Registry. Python modules remain ordinarily importable so the spawned
  server worker can resolve functions. Project packages need distinct Python names.
  A running process does not hot-patch imported functions; development serve --reload
  restarts on changes, and deployment ships reviewed files/dependencies and restarts.
  CLI serve defaults Run storage to the project's `.decision-layer/decision_layer.db`
  rather than an installed-package directory; explicit DL_DATABASE_URL wins.
- Only selected local project code is imported. Definition symlinks stay in the
  project definitions directory. Duplicate identities, malformed exports, invalid
  Skills and missing suggested tools fail with paths before the target registry is
  changed. Python and Skill registrations are staged together, allowing Skill
  references to definitions later in directory order.
- Built-ins and their historical versions remain intact. Legacy DL_METHOD_MODULES /
  METHODS, DL_SKILLS_DIR and managed Web publications remain compatible. Publication
  version/source rules, permissions, Run evidence and interpretation are unchanged.
  No code upload service, package installer, auto-import of every installed package,
  marketplace or new execution engine is added.

The design borrows a marked project/configured paths from
[dbt](https://docs.getdbt.com/reference/dbt_project.yml), a shared project-definition
loader and CLI inspection from
[Dagster's loader](https://github.com/dagster-io/dagster/blob/master/python_modules/dagster/dagster/components/core/load_defs.py),
and explicit discovery boundaries and diagnostic commands from
[pytest](https://docs.pytest.org/en/latest/how-to/writing_plugins.html). Automatic
installed-package entry points are deferred: local team definitions need a visible
project directory before a distribution/plugin ecosystem.


## ADR-107 — Package the existing admin UI with the Python application (2026-10-19)

**Accepted.** A Method project is the local application entry point. `serve` starts
the admin console at `/ui/` and canonical API on one origin. `--api-only` preserves
the lightweight API development path. Existing root REST endpoints stay compatible;
`/api/` mounts the same API instance, caller checks and engine used by REST/MCP.

The existing client React pages are compiled with Vite for distribution, with a
small React Router adapter for their Next navigation imports. Next remains available
for existing Web development/deployment. No parallel Method UI or execution logic
is introduced. Release CI builds the console before wheel/sdist construction, and
installation requires neither Node nor Docker. Missing UI assets fail with a build
remedy, rather than silently presenting an API-only product.

Local persistent state defaults to `.decision-layer/`, Recipes to `recipes/`, with
explicit environment settings taking precedence. Project identity/path are visible
in the console. File-authored Methods are edited in their files; opt-in Web drafts
and immutable publication remain governed by ADR-100 and do not overwrite project
files. Source credentials and editor permissions are not silently enabled. This is
a local application, not a new shared deployment or sandbox.

## ADR-108 — Concise column declarations and invocation-time entities (2026-10-19)

**Accepted.** New ordinary Python registrations use the public
`DataInput(columns={name: Column(...)})` authoring API. `Column.source` is required:
`"measure"`, `"dimension"`, or an explicit list of both. `dtype`, `multiple`,
`required`, and `description` express constraints once. The author-facing models
compile to the existing core DataInput/RoleSpec manifest at registration; they do
not introduce a second engine or change stored manifest formats.

- Matching Column names and function arguments automatically produce the existing
  column_args contract. Ambiguous ownership across tables fails registration;
  explicit column_args can select the owner. An inferred column argument cannot be
  overridden as a calculation option. Fixed-column functions need no extra list.
- `grain="entity"` declares entity observations without a user-invented binding
  alias. It compiles to the canonical entity role named `entity`; the existing
  `entity=...` invocation input on Python/REST/MCP selects the actual provider-owned
  key. Entity identity, joins and aggregation remain provider-owned. Missing keys
  and unsupported grain fail closed. Separate entity roles on multiple tables
  remain available through the advanced legacy declaration.
- Aggregate inputs can declare Column roles too. Actual selected kinds determine
  measure/dimension query fields, preserving list aliases. Returned aggregate grain
  validation uses the resolved dimension aliases; entity grain retains its unique,
  non-null unit/time checks. This never asserts statistical independence.
- Existing measures/dimensions/RoleSpec/explicit column_args and named entity roles
  remain supported, including installed historical implementations. Supersedes the
  author-facing requirement for explicit column_args in ADR-105, not its canonical
  execution/evidence contract. Shared Web discovery reads the normalized manifest.
- DataFrame results use the existing automatic table adapter. Dict estimates remain
  explicit via output="estimate". No dependency installation or new result-type
  inference is introduced. Notebook, CLI scaffold and example project use the same
  authoring path; this source change does not publish a new PyPI version.

## ADR-109 — Declare analysis keys alongside other input columns (2026-10-19)

**Accepted.** The preferred authoring form for entity observations is
`Column(source="dimension", role="entity_key")` inside `DataInput.columns`.
The author chooses its name (for example entity_id or customer_id), and callers
supply the real semantic reference under that same name in bindings. This replaces
ADR-108's preferred grain="entity" / separate entity=... syntax; that syntax and
older explicit entity roles remain compatible.

- source describes allowed semantic kinds; role describes the column's use.
  An entity_key must be one required dimension, backed by a provider-declared
  entity identifier. Each input table allows one key. Conflicting grain/entity
  declarations, multiple keys, optional keys, and measure keys fail registration.
  Time granularity remains separate; a key does not establish independence.
- Registration compiles the key to the existing canonical entity role, retaining
  its constraints and description. The canonical DataInput.entity names that role,
  and its columns entry retains the declared key. No new invocation fields or
  semantic definitions are introduced. Required bindings and provider grain
  validation still run through the ordinary Registry and dataset path.
- The returned key column preserves the author's name. Matching function arguments
  receive that column name like other Column inputs. Alias collisions fail before
  extraction; null/duplicate keys fail before calculation. Legacy tables retain
  their unit alias. Queries, resolved aliases and references remain in provenance.
- Notebook and project examples use bindings for every semantic input. Web shows
  the declared key once and labels its role. Source publication and PyPI release
  remain separate actions; this implementation updates the local repository.

## ADR-110 — Organize learning material and code by responsibility (2026-10-19)

**Accepted.** Learning notebooks live in `docs/tutorials/methods/`. Reusable example
code lives under `examples/methods/authoring`, `statistics`, `scenarios`, and
`examples/recipes`; complete team projects remain under `examples/methods/project`.
The previous `patterns` folder mixed these responsibilities and is removed. Example
and notebook tests belong in `tests/examples`, discovered by the ordinary test run.
VitePress links to tutorial sources and a repository map instead of duplicating
notebook content in generated Markdown.

- Update imports, CLI examples, Docker mounts, CI, formatter targets and links in
  the same change. The complete-journey demo mounts `examples` as an importable
  namespace and loads `examples.recipes.skill_chain`.
- Product authoring exports remain in `decision_layer.methods`. Built-in assembly
  moves to `methods/catalog.py`, re-exporting `register_builtins` at its existing
  public path. Implementation module paths, Method IDs, versions and historical
  evidence remain unchanged. Example modules are repository teaching assets, not
  installed public APIs; local settings referencing them need the new paths.
- Method presentation and editing components live in `web/features/methods`,
  matching Recipe and Run feature ownership. Shared routes still use the same
  components and canonical API. This changes organization, not execution behavior.
- The introductory English notebook follows the current Korean rank/OLS sequence.
  Both are executed from the tutorial directory against prepared data. Advanced
  SDK notebooks remain separate references.

This is a repository organization change, not a new package, provider, execution
engine, UI runtime or PyPI release. Generated frontend assets and local project
state remain separate from editable source.

## ADR-111 — Separate product orchestration from execution policies and presentation (2026-10-19)

**Accepted.** Refactor product implementation by responsibility while preserving
public Python imports, Method manifests, REST/MCP payloads and stored Run schemas.

- PythonMethod delegates canonical registration, provider-side extraction and
  worker-side calculation to `methods/function/`. Option/data check handling is
  shared; expected validation failures stop computation, programming errors still
  propagate, and existing validation codes/messages remain intact.
- RunEngine retains lifecycle, locks, jobs and pipeline resumption. Step execution,
  context creation, budgets/scope and read authorization have separate modules with
  explicit dependencies. Shared Run reads still check every recorded semantic ref;
  query attempts are still persisted before the provider call. Errors remain
  re-exported from their existing engine import path.
- MCP evidence projection is separate from registered tools and HTTP dispatch.
  Projection never modifies stored results or performs queries. Instruction text
  is kept separately, using the same locale and client-profile selection.
- API host/origin/locale handling and operator permission checks have dedicated
  modules; Method and Recipe permissions share the same explicit local-owner rule.
  CLI file scaffolding is separate from argument dispatch and serving, with the
  existing Python entry points retained.
- Recipe editing separates graph nodes, reusable field controls, step settings and
  pure editor values. The parent retains mutation/preview state so asynchronous
  configuration and YAML conflict checks keep their existing behavior.

No new runtime, public abstraction or interface-specific execution path is added.
Existing integration tests cover worker execution, private/shared Run access, Skill
continuations, API errors and MCP payloads. Regression tests pin check ordering and
programming-error behavior; browser checks cover Recipe edits and saved selections.

## ADR-112 — Start the installed product with optional packaged sample data (2026-10-19)

**Accepted.** PyPI installation is the primary user path. `decision-layer demo`
uses bundled SQL, Cube models and Compose configuration to start only PostgreSQL
and Cube in Docker. Web/API run from the installed Python package on loopback,
using the same console, REST endpoints, execution engine and SQLite Run store.
The existing scripted walkthrough is packaged and reused by the repository demo.

The sample has its own marked project directory, Docker project and local state.
It does not inherit configured organization sources, credentials, Methods or
Recipes. An unmanaged directory is never overwritten. Ctrl+C stops its server
and containers; volumes, Recipes and Runs remain. `demo stop` stops leftover data
services after an interrupted start. No clone, Node.js or product image build is
required. The all-Docker repository example remains a contributor/reference path.

Documentation starts with installation, then offers sample data or an existing
Cube connection. Sample PostgreSQL contains source observations; SQLite records
Decision Layer execution. This adds onboarding commands, not a semantic provider,
analysis engine or service scheduler.

## ADR-113 — Keep one Method authoring path and remove obsolete public labs (2026-10-19)

**Accepted.** The developer navigation contains three tasks: write a Python
Method, use a Method project, and contribute to the product. SDK patterns,
discovery, deployment, repository maps and test instructions are consolidated
into those guides and the existing contract/architecture references.

Remove the CEM/PyWhy review report and its estimator-comparison lab, result dumps,
constraints and notebook. Remove superseded advanced, query-scenario and SDK
notebooks; retain the bilingual ordinary-function tutorial and complete project.
These are deletions, not hidden public pages or another documentation archive.

Executable SDK and numerical fixtures still needed to verify product behavior
belong to tests/support/methods. Refusal cases run as pytest cases instead of a
separate example CLI. Remove unused experiment servers, live research runners and
old notebook-compatibility helpers. Shared introductory data lives beside the
retained authoring example. Production Methods, historical Method contracts and
recorded Runs are unaffected.
