"""Shared conversion of recorded selection paths to semantic filters."""
from typing import Any
from ..core.models import Filter
from .context import ExecutionContext, Refused
from ..i18n import _


def path_filters(ctx: ExecutionContext, drill_path: list[dict[str, Any]] | None) -> list[Filter]:
    """drill_path = [{member: ref, value: v}, …] → equality filters (the branch chosen so far)."""
    out = []
    for step in drill_path or []:
        if not isinstance(step, dict) or "member" not in step or "value" not in step:
            raise Refused(_("drill_path items must be {{member, value}}"))
        ctx.obj(step["member"])
        out.append(Filter(member=step["member"], operator="equals", values=[step["value"]]))
    return out
