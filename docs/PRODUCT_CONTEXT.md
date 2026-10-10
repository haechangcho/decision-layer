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
| Method | An atomic analytical capability with typed inputs, execution, validation and outputs |
| Recipe | A reusable procedure using existing Methods and semantic references |
| Run | One question/invocation, execution steps, versions, queries and evidence |
| Result | Renderer-neutral analytical artifacts, validation and limitations |
| Validator | A reusable check on data, execution or analytical assumptions |

A Method can request multiple datasets and combine them. A Recipe selects and
configures Methods according to an organization's investigation procedure. Do not
create a new Method when existing capabilities and a Recipe are sufficient.

## Users and development experience

Analysts reuse Recipes and inspect results. Senior analysts encode procedures.
Method contributors use ordinary Python modules, pytest and optional Jupyter/VS Code.
The first development example needs no Web server or live provider. Web helps select
semantic inputs, create procedures and inspect recorded execution.

AI clients select registered Methods/Recipes and existing semantic objects. They may
plan and narrate, but generated analytical Python or SQL is not the normal execution
path. Developer code runs as reviewed installed implementations or trusted local trials.

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
not duplicate frontend/API/MCP logic. Current sources are Cube REST and official dbt
Semantic Layer GraphQL. Native metadata may limit supported statistical workloads.

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
