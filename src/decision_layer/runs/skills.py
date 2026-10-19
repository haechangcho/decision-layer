"""Agent-driven Skill steps with recorded, governed queries and evidence-bound exports.

No Markdown interpreter or hidden analytic Python implementation. The client agent
chooses queries; this module enforces the shared scope and records what ran.
"""
from datetime import datetime, timezone
from typing import Literal
import math

from pydantic import BaseModel, ConfigDict, Field
from ..core.models import (Artifact, ArtifactColumn, DatasetSpec, Filter, Provenance, Result,
    SelectionCandidate, SelectionCondition, SelectionOutput, SkillQueryRecord, ValidationResult, ExecutionAuthor)
from ..core.errors import DecisionLayerError
from ..methods import InvalidBinding


def now():
    return datetime.now(timezone.utc)


class SkillQueryRequest(BaseModel):
    author: ExecutionAuthor | None = None
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    purpose: str = Field(min_length=1, max_length=600)
    spec: DatasetSpec
    period_role: Literal["current", "comparison"] = "current"


class SkillSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query_id: str
    row: int = Field(ge=0)
    dimension: str
    reason: str = Field(min_length=1, max_length=600)


class SkillFinishRequest(BaseModel):
    author: ExecutionAuthor | None = None
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "refused"] = "completed"
    reason: str = Field(min_length=1, max_length=1200)
    selection: SkillSelection | None = None


def active(run, step_id):
    if run.status != "open" or run.active_skill_step != step_id:
        raise InvalidBinding("This is not the active Skill step.")
    record = next((r for r in run.steps if r.step.id == step_id), None)
    if not record or not record.skill or record.skill.status != "awaiting_agent":
        raise InvalidBinding("The Skill step is not awaiting an agent.")
    return record


async def query(engine, creds, run, step_id, req, author=None):
    record = active(run, step_id)
    previous = next((q for q in record.skill.queries if q.id == req.id), None)
    if previous:
        if previous.spec != req.spec or previous.purpose != req.purpose or previous.period_role != req.period_role:
            raise InvalidBinding("Query ID already records a different request.")
        return previous
    if len(record.skill.queries) >= 12:
        raise InvalidBinding("This Skill step reached its 12 query-attempt limit.")
    item = SkillQueryRecord(**req.model_dump(exclude={"author"}), author=author or req.author)
    record.skill.queries.append(item)
    await engine.store.save(run)
    ctx = None
    try:
        ctx = await engine._context(creds, run)
        ctx.step_id = step_id
        spec = req.spec
        if spec.grain != "aggregate" or spec.entity:
            raise InvalidBinding("Skill queries use aggregate Cube reads; use a registered Python Method for entity analysis.")
        if not spec.measures or spec.limit_rows is None or not 1 <= spec.limit_rows <= min(1000, engine.policy.max_result_rows):
            raise InvalidBinding("Select measures and an explicit row limit between 1 and the server limit (at most 1000).")
        if not spec.time or not spec.time.date_range:
            raise InvalidBinding("Skill queries require an explicit period and time dimension.")
        expected = tuple(run.plan.scope.get("date_range") or ()) if req.period_role == "current" else tuple(record.step.params.get("comparison") or ())
        if not expected or tuple(spec.time.date_range) != expected:
            raise InvalidBinding("Query dates must equal the Run period, or the Skill's explicitly bound comparison period.")
        if run.plan.scope.get("time_dimension") and spec.time.dimension != run.plan.scope['time_dimension']:
            raise InvalidBinding("Query time dimension must match the Run scope.")
        manifest = record.skill.manifest
        allowed = set()
        for name, role in manifest.roles.items():
            if role.kind == "measure":
                value = record.step.bindings.get(name, [])
                allowed.update([value] if isinstance(value, str) else value)
        for ref in list(allowed):
            count = ctx.obj(ref).count_measure
            if count: allowed.add(count)
        if not set(spec.measures) <= allowed:
            raise InvalidBinding("Skill queries must use their bound metrics or provider-declared count measures.")
        for condition in record.step.params.get("population", []):
            required = Filter(member=condition['member'], operator="equals", values=[condition['value']])
            if required not in spec.filters:
                raise InvalidBinding("Query omitted the population inherited by this Skill step.")
        for raw_filter in record.step.params.get("filters", []):
            if Filter.model_validate(raw_filter) not in spec.filters:
                raise InvalidBinding("Query omitted inherited filters.")
        dataset = await ctx.dataset(spec, with_sql=True, label=f"skill:{req.id}")
        columns = [ArtifactColumn(name=c.ref, ref=c.ref, role=c.role, granularity=c.granularity) for c in dataset.columns]
        rows = [dict(zip([c.ref for c in dataset.columns], row)) for row in dataset.rows]
        refs = list(dict.fromkeys([*spec.measures,*spec.dimensions, spec.time.dimension,*(f.member for f in spec.filters)]))
        checks = [ValidationResult(validator="skill.query_scope@1",code="QUERY_SCOPE", status="pass",
                                  message="Bound metrics, period, inherited population and provider query checks executed.")]
        item.result = Result(status="success", interpretation="association", primary=Artifact(type="table",data=rows,columns=columns,title=req.purpose),
            validation=checks, warnings=["Returned rows are a bounded query result, not proof of complete population, appropriate peers or causal validity."],
            provenance=Provenance(method=record.method,semantic_refs=refs,queries=ctx.queries),run_id=run.id,step_id=step_id)
        item.status = "success"
    except BaseException as exc:
        item.status = "failed" if isinstance(exc, Exception) else "interrupted"
        item.error = {"code": exc.code if isinstance(exc, DecisionLayerError) else "QUERY_INTERRUPTED" if not isinstance(exc, Exception) else "QUERY_FAILED",
                      "message": exc.message if isinstance(exc, DecisionLayerError) else "Query failed or was interrupted; inspect the provider and retry with a new query ID."}
        if not isinstance(exc, Exception): raise
    finally:
        item.finished_at = now()
        refresh(record, run)
        await engine.store.save(run)
    return item


def refresh(record, run):
    outputs = [q.result for q in record.skill.queries if q.result]
    record.result.provenance.queries = [p for r in outputs for p in r.provenance.queries]
    record.result.provenance.semantic_refs = list(dict.fromkeys([*record.result.provenance.semantic_refs,
        *(ref for r in outputs for ref in r.provenance.semantic_refs)]))
    record.result.validation = [v for r in outputs for v in r.validation]
    record.result.artifacts = [r.primary for r in outputs if r.primary]


def finish(engine, run, step_id, req, author=None):
    record = active(run, step_id)
    queries = record.skill.queries
    if any(q.status == "running" for q in queries):
        raise InvalidBinding("Wait for the query to finish.")
    successful = [q for q in queries if q.status == "success" and q.result and q.result.primary and q.result.primary.data]
    if req.status == "completed" and not successful:
        raise InvalidBinding("A completed Skill needs non-empty recorded query evidence; otherwise refuse it.")
    if req.status == "refused" and req.selection:
        raise InvalidBinding("A refused Skill cannot export a selected group.")
    result = record.result.model_copy(deep=True)
    if req.selection:
        sel = req.selection
        source = next((q for q in successful if q.id == sel.query_id), None)
        if not source or sel.dimension not in source.spec.dimensions or sel.row >= len(source.result.primary.data):
            raise InvalidBinding("Selection must point to a returned dimension value of a successful query.")
        value = source.result.primary.data[sel.row].get(sel.dimension)
        if value is None or not isinstance(value, (str,int,float,bool)) or isinstance(value,(int,float)) and not math.isfinite(value):
            raise InvalidBinding("The selected group needs a finite non-null scalar value.")
        path = [SelectionCondition(member=f.member,value=f.values[0]) for f in source.spec.filters
                if f.operator == "equals" and len(f.values)==1 and f.member != sel.dimension]
        path.append(SelectionCondition(member=sel.dimension,value=value))
        result.selections['selected_group'] = SelectionOutput(kind="selected_group",complete=True,
            rank_by="agent_selected_from_query",direction="desc",candidates=[SelectionCandidate(path=path,score=0)],
            reason=sel.reason,evidence={'query_id':sel.query_id,'row':sel.row,'dimension':sel.dimension,'scope':'returned_rows_only', 'filters':[f.model_dump(mode='json') for f in source.spec.filters] + [Filter(member=sel.dimension,operator='equals',values=[value]).model_dump(mode='json')]})
    if req.status == "completed":
        rows = [{'query':q.id, **row} for q in successful for row in q.result.primary.data]
        result.primary = Artifact(type="table", title="Recorded Skill query results",data=rows)
    result.status = "success" if req.status == "completed" else "refused"
    result.needs_input = None
    result.interpretation = "association"
    result.provides = []  # No analytical capability is certified by reading prose.
    result.warnings = ["Skill adherence, peer suitability, source completeness and causal assumptions are not verified. Only recorded query checks executed."]
    if any(q.status != "success" for q in queries):
        result.warnings.append("Some query attempts failed or were interrupted; their errors remain in this step's log.")
    record.result = result
    record.skill.status, record.skill.completion_reason, record.skill.completed_by = req.status, req.reason, author or req.author
    record.finished_at = now()
    run.active_skill_step = None
    return result
