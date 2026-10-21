# Shared analysis execution

This is the product's tool protocol. Follow it together with the active Skill's
analysis procedure. Skill authors describe the analysis; they do not need to copy
these instructions into each SKILL.md. These instructions grant no permissions.

## Confirm the inputs

- Read the active step's bindings and parameters, the Run period and shared filters.
  Keep inherited population and filter conditions in every relevant query.
- Use search_semantic to discover missing metrics, dimensions and time dimensions.
  Read their definitions and types. Never invent fields, formulas or joins, or
  silently substitute another metric. Ask when the requested meaning is ambiguous.
- Query only bound metrics (or their provider-declared count measures). If the
  question needs another metric, resolve its binding before running the step.

## Query and inspect

1. Use the active Run and step identifiers returned by the server. Call
   run_skill_query with a unique query ID, purpose and an aggregate DatasetSpec:
   measures, discovered dimensions, explicit time.dimension/date_range, filters,
   optional order, and limit_rows between 1 and 1000 (subject to server policy).
   Current dates must match the Run. Comparison dates must match the step's
   explicit comparison parameter; set period_role="comparison" for that query.
2. Read status, validation, warnings and returned rows. The first response includes
   up to 25 rows; use get_skill_query with next_offset to read more. A bounded
   result does not establish that every group or observation was returned.
3. Failed or interrupted queries remain recorded. Correct a request under a new
   query ID. Reusing an ID cannot change its request. Stop unsupported claims;
   never bypass refusal with generated Python, SQL or unregistered calculations.

## Finish with evidence

- Call finish_skill_step with a reason. Use status="refused" if evidence is missing
  or unsuitable. Successful completion requires non-empty recorded query results.
- To pass a group to the next step, select a successful query's real row: query_id,
  absolute zero-based row index, dimension and reason. Add the page offset when
  using a paged response. Preserve selected_group.evidence.filters for the full
  population, including exclusions and range filters.
- Do not start another step while a Skill is active. Completion resumes a waiting
  Recipe. After interruption, read get_run before continuing.
- Summarize only supported results and cite recorded evidence. Query success does
  not prove adherence to the analysis procedure, complete source data, suitable
  comparisons or causality. Follow the Result's interpretation and limitations.

The server independently enforces semantic access, bindings, scope, inherited
conditions, query budgets and evidence references. This shared guide and individual
Skill text remain advisory; reading either is not executed validation.
