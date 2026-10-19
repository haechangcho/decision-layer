"""Owner-only writes and semantic visibility checks for shared Run reads."""

from __future__ import annotations
from ..core.errors import ProviderAccessDenied
from ..core.models import Run, CallerInfo
from ..i18n import _
from .store import UnknownRun


def _owns(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and run.caller.subject == caller.subject


def _shared_with(run: Run, caller: CallerInfo) -> bool:
    return bool(caller.subject) and (
        caller.subject in run.shared_with or "*" in run.shared_with
    )


async def owned_run(store, run_id: str, caller: CallerInfo) -> Run:
    run = await store.get(run_id)
    if not _owns(run, caller):
        raise UnknownRun(_("Run not found: {run_id}", run_id=run_id))
    return run


async def visible_run(store, provider, creds, caller: CallerInfo, run_id: str) -> Run:
    """Owner, or a viewer the run is shared with whose catalog covers everything it used."""
    run = await store.get(run_id)
    if _owns(run, caller):
        return run
    if not _shared_with(run, caller):
        raise UnknownRun(
            _("Run not found: {run_id}", run_id=run_id)
        )  # same answer as a missing run
    visible = {o.ref for o in (await provider.discover(creds)).objects if o.public}
    from ..recipes.routing import semantic_refs

    used = {r for s in run.steps for r in s.result.provenance.semantic_refs}
    used.update(
        semantic_refs(
            [attempt.spec.model_dump(mode="json") for attempt in run.query_attempts]
        )
    )
    used.update(ref for goal in run.goals for ref in goal.semantic_refs)
    used.update(
        semantic_refs(
            [
                q.spec.model_dump(mode="json")
                for record in run.steps
                if record.skill
                for q in record.skill.queries
            ]
        )
    )
    used.update(semantic_refs(run.recipe_candidates))
    used.update(
        semantic_refs([item.model_dump(mode="json") for item in run.remediations])
    )
    if run.retry_of:
        used.update(semantic_refs(run.retry_of.model_dump(mode="json")))
    hidden = sorted(used - visible)
    if hidden:
        raise ProviderAccessDenied(
            _("This run uses measures or dimensions you don't have access to"),
            count=len(hidden),
        )
    return run
