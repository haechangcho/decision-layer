"""Owner-reviewed semantic requirements, not generated semantic definitions."""
import asyncio
from datetime import datetime, timezone

from ..core.ids import new_id
from ..core.models import AnalysisPlan, Run, RunRemediation, RunRetryLink
from ..methods.base import InvalidBinding


async def record_blocked(engine, caller, req, origin):
    """Save a diagnosis in one write; no data queries or invented analytical results."""
    from .goals import validate_outcomes
    if len({goal.id for goal in req.goals}) != len(req.goals):
        raise InvalidBinding("Goal IDs must be unique.")
    # An existing question-scoped Run may have supported goals and partial results.
    lock_id = req.run_id or new_id("run")
    async with engine._scope_locks.setdefault(lock_id, asyncio.Lock()):
        if req.run_id:
            run = await engine._owned(req.run_id, caller)
            ensure_idle(run)
            if run.status != "open" or run.plan.question != req.question or run.goals != req.goals:
                raise InvalidBinding("Use the existing open Run's original question and goals.")
        else:
            run = Run(id=lock_id, origin=origin, caller=caller, author=req.author,
                goals=req.goals, interactive=True, plan=AnalysisPlan(question=req.question))
            engine._prepare_scope(run, req.scope.as_dict())
        validate_outcomes(run, req.conclusion)
        if any(not finding.step_indices or any(index < 0 or index >= len(run.steps) for index in finding.step_indices)
               for finding in req.conclusion.findings):
            raise InvalidBinding("Conclusion findings must link to recorded steps.")
        if run.steps and not req.conclusion.findings:
            raise InvalidBinding("Keep evidence-linked findings for the steps already executed.")
        unresolved = {outcome.goal_id: outcome for outcome in req.conclusion.goal_outcomes if outcome.status != "supported"}
        if not unresolved or any(not outcome.reason_code for outcome in unresolved.values()):
            raise InvalidBinding("Record a classified reason for each unresolved goal.")
        if not req.run_id and req.conclusion.findings:
            raise InvalidBinding("A blocked analysis without executed steps cannot record findings.")
        gaps = {gap.goal_id: gap for gap in req.semantic_gaps}
        if len(gaps) != len(req.semantic_gaps):
            raise InvalidBinding("Record at most one semantic proposal per goal.")
        semantic = {goal_id for goal_id, outcome in unresolved.items() if outcome.reason_code == "semantic_missing"}
        existing = {goal_id for item in run.remediations for goal_id in [item.goal_id, *item.related_goal_ids]}
        covered = {goal_id for gap in gaps.values() for goal_id in [gap.goal_id, *gap.related_goal_ids]}
        if sum(1 + len(gap.related_goal_ids) for gap in gaps.values()) != len(covered):
            raise InvalidBinding("Combine shared requirements in one proposal; a goal cannot appear twice.")
        if covered - semantic or semantic - (covered | existing):
            raise InvalidBinding("Semantic gaps need evidence and typed requirements; other failure reasons must not create model proposals.")
        if len(run.remediations) + len(gaps) > 12:
            raise InvalidBinding("A Run may contain at most 12 model improvement records.")
        for gap in gaps.values():
            if {gap.goal_id, *gap.related_goal_ids} & existing:
                raise InvalidBinding("This goal already has a proposal. Review it rather than overwriting it.")
            run.remediations.append(RunRemediation(id=new_id("fix"), **gap.model_dump(),
                events=[event(caller, "proposed", origin=origin, proposal=gap.model_dump(mode="json"))]))
        run.conclusion = req.conclusion.model_copy(update={"source": "caller"})
        run.conclusion_author = req.author
        run.summary = run.conclusion.answer
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        run.needs_input, run.pending_execution = None, None
        await engine.store.save(run)
        return run


def find(run, remediation_id, revision):
    item = next((item for item in run.remediations if item.id == remediation_id), None)
    if item is None:
        raise InvalidBinding("Unknown model improvement record.")
    if item.revision != revision:
        from .engine import RunBusy
        raise RunBusy("The improvement record changed. Reload it before continuing.")
    return item


def event(caller, action, **details):
    return {"at": datetime.now(timezone.utc).isoformat(), "subject": caller.subject,
            "action": action, **details}


async def create(engine, caller, run_id, req):
    async with engine._scope_locks.setdefault(run_id, asyncio.Lock()):
        run = await engine._owned(run_id, caller)
        ensure_idle(run)
        goal = next((goal for goal in run.goals if goal.id == req.goal_id), None)
        if goal is None or set(req.related_goal_ids) - {goal.id for goal in run.goals}:
            raise InvalidBinding("An improvement must address a recorded goal.")
        if len(run.remediations) >= 12:
            raise InvalidBinding("A Run may contain at most 12 model improvement records.")
        item = RunRemediation(id=new_id("fix"), **req.model_dump(),
            events=[event(caller, "proposed", origin=run.origin, proposal=req.model_dump(mode="json"))])
        run.remediations.append(item)
        await engine.store.save(run)
        return run


def ensure_idle(run):
    if run.running or run.preview:
        from .engine import RunBusy
        raise RunBusy("Wait for execution to finish; previews cannot manage model improvements.")


async def review(engine, caller, run_id, remediation_id, req):
    async with engine._scope_locks.setdefault(run_id, asyncio.Lock()):
        run = await engine._owned(run_id, caller)
        ensure_idle(run)
        item = find(run, remediation_id, req.base_revision)
        item.status = req.decision
        item.requirements = req.requirements
        item.revision += 1
        item.events.append(event(caller, "reviewed", decision=req.decision, note=req.note,
                                  requirements=[r.model_dump(mode="json") for r in req.requirements]))
        await engine.store.save(run)
        return run


async def check(engine, creds, caller, item):
    if item.status != "confirmed":
        raise InvalidBinding("Review and confirm the model improvement before checking it.")
    refresh = getattr(engine.provider, "refresh_catalog", engine.provider.discover)
    catalog = await refresh(creds)
    results = []
    for required in item.requirements:
        obj = catalog.get(required.ref) if required.ref else None
        issues = []
        if obj is None or not obj.public:
            issues.append("not_visible")  # absence and permission cannot be distinguished by metadata
        else:
            if obj.kind != required.kind:
                issues.append("kind_mismatch")
            if required.data_type and obj.data_type != required.data_type:
                issues.append("type_mismatch")
            if required.metric_kind and obj.metric_kind != required.metric_kind:
                issues.append("metric_kind_mismatch")
            if required.needs_entity:
                entity = catalog.get(obj.entity) if obj.entity else None
                if entity is None or not entity.public:
                    issues.append("queryable_entity_unknown")
            if required.needs_time:
                time = catalog.get(obj.time_dimension) if obj.time_dimension else None
                if time is None or not time.public or time.kind != "time_dimension":
                    issues.append("time_dimension_unknown")
        results.append({"description": required.description, "ref": required.ref,
                        "title": obj.title if obj and obj.public else None, "issues": issues})
    snapshot = event(caller, "checked", revision=item.revision, provider=catalog.provider,
        instance=catalog.instance, discovered_at=catalog.discovered_at.isoformat(),
        ready=all(not result["issues"] for result in results), results=results,
        boundary="Metadata only; execution still validates joins, grain, data and Method assumptions.")
    item.checks.append(snapshot)
    return snapshot


async def recheck(engine, creds, caller, run_id, remediation_id, req):
    async with engine._scope_locks.setdefault(run_id, asyncio.Lock()):
        run = await engine._owned(run_id, caller)
        ensure_idle(run)
        item = find(run, remediation_id, req.base_revision)
        await check(engine, creds, caller, item)
        item.revision += 1
        await engine.store.save(run)
        return run


async def retry(engine, creds, caller, run_id, remediation_id, req, origin, wait):
    async with engine._scope_locks.setdefault(run_id, asyncio.Lock()):
        run = await engine._owned(run_id, caller)
        ensure_idle(run)
        item = find(run, remediation_id, req.base_revision)
        snapshot = await check(engine, creds, caller, item)
        item.revision += 1
        await engine.store.save(run)
        if not snapshot["ready"]:
            raise InvalidBinding("Model requirements are not yet visible or compatible.", checks=snapshot)
        if req.question and req.question != run.plan.question:
            raise InvalidBinding("A linked retry must keep the original question.")
        if req.goals:
            before = {goal.id: (goal.description, goal.required_capabilities, goal.interpretation) for goal in run.goals}
            after = {goal.id: (goal.description, goal.required_capabilities, goal.interpretation) for goal in req.goals}
            if before != after:
                raise InvalidBinding("A linked retry must keep the original goals and interpretation; only semantic references may change.")
        # Do not replay old literal selections or silently rebind references to a new model.
        scope = dict(run.plan.scope)
        scope.pop("inputs", None)  # Runtime targets must be supplied again, not remembered from old data.
        if req.scope.model_fields_set:
            override = req.scope.as_dict()
            if "period" in override or "date_range" in override:
                scope.pop("period", None)
                scope.pop("date_range", None)
            scope.update(override)
        new = await engine.start(creds, caller, recipe=req.recipe, question=run.plan.question,
            scope=scope, goals=req.goals or run.goals, author=req.author, origin=origin,
            recipe_selection=req.recipe_selection, recipe_review=req.recipe_review,
            interactive=True, wait=wait,
            retry_of=RunRetryLink(run_id=run.id, remediation_id=item.id,
                remediation_revision=item.revision, checked_at=snapshot["at"],
                requirements=item.requirements))
        item.events.append(event(caller, "retry_started", run_id=new.id))
        await engine.store.save(run)
        return new
