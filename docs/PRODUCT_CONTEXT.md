# Product context

Decision Layer is an open-source analytics knowledge and execution layer above a
semantic layer. It makes organizational analytical procedures executable, inspectable,
versionable and reusable by people and AI agents.

> Connect governed metrics, encode how your team investigates recurring questions,
> and execute the same procedure through Web, Python, REST or MCP.

## Problem and value

Semantic systems define what data means. Statistical libraries compute algorithms.
Between them, analysts repeatedly apply procedural knowledge: compare complete
periods, break changes down, investigate a selected branch, check related metrics,
and state limitations. This knowledge often lives in individual notebooks and chats.

Decision Layer connects that knowledge to governed data and records its execution.
The near-term value is reusable organizational analysis, with statistical/causal
Methods as primitives where data and assumptions support them.

## Core objects

| Object | Owns |
| --- | --- |
| Semantic source/catalog | Provider-owned definitions, dimensions, grain, access and discoverable references |
| Method | A reusable asset: Python capability or Skill guiding recorded Cube queries |
| Recipe | A reusable procedure using existing Methods and semantic references |
| Run | One question/invocation, execution steps, versions, queries and evidence |
| Result | Renderer-neutral analytical artifacts, validation and limitations |
| Validator | A reusable check on data, execution or analytical assumptions |

A Python Method can request multiple datasets and combine them. A query-executing
Skill guides an AI through recorded, scoped Cube queries in a Run step. Advisory-only
Skills remain reference material. Reading prose never verifies its claims. A Recipe selects and
configures Methods according to an organization's investigation procedure. Do not
create a new Method when existing capabilities and a Recipe are sufficient.

## Users and development experience

Analysts reuse Recipes and inspect results. Senior analysts encode procedures.
Method contributors use ordinary Python modules, pytest and optional Jupyter/VS Code.
New team definitions use one Method project: Python method.py entries and Skill
SKILL.md entries share a root-level `methods/` directory, alongside `recipes/` and `decision-layer.yaml`. The project name does not require a second nested source directory (ADR-120). Scaffold, check, list, local loading
and API startup share project discovery (ADR-106).
Ordinary Python functions register through separate DataInput declarations; advanced typed
functions remain supported. Input maps reference governed objects.
Functions may retain ordinary column-name arguments, including lists of covariates.
New registrations declare explicit Column sources and constraints in DataInput.columns;
matching function arguments receive resolved column names automatically. Entity-level
methods declare a Column with source="dimension" and role="entity_key"; callers
select its actual reference through the same named bindings as other variables.
These declarations compile to the shared manifest and validation contracts (ADR-108/109). Legacy declarations remain supported. AI selects semantic bindings;
grain and variable meaning are not guessed from a Python signature alone.
The first development example needs no Web server or live provider. Web helps select
semantic inputs, create procedures and inspect recorded execution.

AI clients select registered Methods/Recipes and existing semantic objects. They may
plan and narrate, but generated analytical Python or SQL is not the normal execution
path. Developer code runs as reviewed installed implementations or trusted local trials.

Statistical contributors use external libraries through their native Python APIs.
Decision Layer supplies governed data and execution contracts; builtin calculation
helpers are implementation details, not a required parallel estimator API.

## Example procedure

A revenue investigation can compare periods, break change down by product, let the
caller select a relevant branch, then inspect that branch by region. Preferred
metrics/dimensions and procedural rules belong to the Recipe; metric formulas and
joins stay in the source. Results record the actual settings and queries.

This is descriptive investigation unless a separately justified Method and its
assumptions support a stronger claim. A difference, selected extreme or matched
comparison alone does not prove a cause.

## Boundaries

The semantic layer owns metric definitions, joins, grain and permissions. Decision
Layer owns analytical procedures, validation, execution and provenance. Provider
aggregation/filtering is preferred; materialization is bounded to Method needs.
Missing semantics or assumptions must fail closed or produce explicit limitations.

All interfaces share canonical contracts and execution rules. Adding a Method should
not duplicate frontend/API/MCP logic. The initial product supports Cube REST only (ADR-096). Existing dbt adapter
code is retained for legacy contract regression, not offered as a product connection. Native metadata may limit supported statistical workloads.

The MVP excludes notebook hosting, unrestricted agents, semantic-model editing,
BI/dashboard building, generic scheduling/DAG engines and custom frontend plugins.

## Success criteria

- A contributor can run, modify and test a Method from a fresh clone.
- An organization connects its semantic source and encodes a recurring procedure.
- Another analyst or AI client reuses that Recipe with inspectable evidence.
- New Methods using existing contracts do not require separate interface logic.
- Users understand refused/limited answers instead of receiving unsupported claims.

See [Architecture](ARCHITECTURE.md) for current code ownership and
[Decisions](DECISIONS.md) for detailed accepted behavior.

Method authoring exposes ordinary typed Python arguments and native statistical-library APIs. Current statistical experiments report association with unverified identification assumptions; assumption checkboxes are not evidence. Semantic validation, execution bounds and provenance remain mandatory (ADR-084).

## Default MVP Methods

Offer two query-executing Skills: analysis.metric_lookup and analysis.drilldown.
Trend, peer comparison and advisory-only guides remain compatibility lookups, not
new discovery choices (ADR-115). Shared Cube tools execute their
queries. Period-change and series-diagnostic calculations are compatibility-only
(ADR-103); Skills must stop claims that require unavailable calculations. Legacy query.aggregate, query.trend, query.drilldown
and query.peer_comparison remain available to pinned Recipes (ADR-099). New projects generate editable metric/drilldown Skills and OLS/matching Python files with calculation tests. OLS uses statsmodels and matching uses scikit-learn; both report association with unverified causal assumptions. Earlier DoWhy implementations remain available to their pinned versions (ADR-116). Peer comparisons, unit analyses and other
statistical estimators are optional reviewed implementations, enabled by normal
Python registration when needed. Existing explicit Recipe contracts retain compatible
execution. A plugin marketplace or Web code installer is outside this MVP (ADR-090).

The first revised-PRD increment adds native synchronous calculation registration,
Codex sample setup, and draft-first MCP procedure saving/publication. Only local
and isolated demo deployment are supported; shared deployment is blocked pending
its authentication/isolation gates. Source administration requires a configured
key and operator-approved endpoint; Recipe writes have explicit permissions and
recoverable retirement (ADR-094/095). dbt, direct DW/DM/BigQuery and SQL AST enforcement
are outside the initial implementation, subject to a later demand-driven decision. Local data-file input is excluded.

## Implemented Method authoring revision (ADR-097)

Method discovery now includes advisory Skill assets and executable Python assets.
Simple investigations can guide existing tools with Markdown. New calculations
start as ordinary Python functions, registered separately with `python_method` and
`DataInput`; multiple inputs and executable pre-calculation checks are supported.
The same engine handles extraction and calculation. Advanced Methods remain valid.

Skill reading is not an execution or validation result. ADR-098 extends this model:
query_execution Skills are Recipe stages with manifest/text/hash snapshots and
per-query requests, results, errors and agent attribution. The pipeline waits for
Claude/Codex to call run_skill_query and finish_skill_step, then resumes. It does not
run an autonomous model on the server. A selection must reference an actual returned
row; its complete filters can feed a later ordinary Python function. Fixed steps
remain repeatable, but agent choices can vary and must be reviewed on rerun.
Operator-owned Git assets and an opt-in local Method editor are implemented. Web
shows registered Python source and rendered Skill Markdown, saves drafts, checks
syntax/registration and publishes immutable versions (ADR-100). Method publisher
permission is separate from Recipe publication. Shared untrusted-code hosting is not supported.

Method detail starts with the selected analysis's authorable function/registration,
not the entire framework module. Exact source evidence is separately expandable.
The retired series diagnostic retains its source-aware adapter for pinned execution.
The general contributor entry remains `python_method` and `DataInput` (ADR-101).

ADR-102 standardizes new calculations on ordinary functions + explicit DataInput.
DoWhy matching/regression 1.1.0 now actually use that runtime. REST/MCP/Web expose the
same executable input table contracts: columns, row meaning and query inputs remain
separate from function options. AI may propose semantic bindings but type checks do
not verify business meaning. Two justified time-analysis source adapters remain;
legacy implementations and saved versions stay available without appearing as new
choices. See the dated method audit for actual retained Run references.
