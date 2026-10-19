"""Read-only Method candidates from existing contracts, never a language router."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..core.interpretation import supports_interpretation
from ..core.models import AnalysisGoal
from .context import ExecutionContext
from .dependencies import dependency_issue
from .registry import InvalidBinding, MethodRegistry


class MethodSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: AnalysisGoal | None = None
    names: list[str] | None = Field(default=None, max_length=200)


def find_methods(registry: MethodRegistry, ctx: ExecutionContext, request: MethodSearchRequest) -> dict:
    """Inspect caller-visible metadata without running Methods or querying rows.

    Description relevance, variable roles and identification assumptions remain
    caller decisions. A single candidate is not an automatic selection.
    """
    manifests = sorted(registry.manifests(), key=lambda item: item.name)
    if request.names is not None:
        manifests = [m for m in manifests if m.name in request.names]
    goal = request.goal
    requested = goal.semantic_refs if goal else []
    for ref in requested:
        ctx.obj(ref)  # Same unknown/private-object boundary as execution.
    capabilities: dict[str, list[str]] = {}
    for manifest in manifests:
        for capability in manifest.provides:
            capabilities.setdefault(capability, []).append(manifest.name)
    candidates, excluded = [], []
    visible = [obj for obj in ctx.catalog.objects if obj.public]
    for manifest in manifests:
        reasons = []
        if goal:
            missing = sorted(set(goal.required_capabilities) - set(manifest.provides))
            if missing:
                reasons.append({"code": "CAPABILITY_MISMATCH", "values": missing})
            if not supports_interpretation(goal.interpretation, manifest.interpretation):
                reasons.append({"code": "INTERPRETATION_MISMATCH"})
        for capability in manifest.requires_capabilities:
            if not getattr(ctx.provider.capabilities(), capability, False):
                reasons.append({"code": "PROVIDER_CAPABILITY_UNAVAILABLE", "value": capability})
        if issue := dependency_issue(manifest.requires_packages):
            reasons.append({"code": "DEPENDENCY_UNAVAILABLE", "message": issue})
        input_candidates = {}
        for name, role in manifest.roles.items():
            matching = []
            for obj in visible:
                try:
                    MethodRegistry.check_role(name, role, obj, ctx.catalog)
                except InvalidBinding:
                    continue
                matching.append(obj.ref)
            # Do not dump the whole catalog or guess which variable has which role.
            input_candidates[name] = [ref for ref in requested if ref in matching]
            if role.required and not matching:
                reasons.append({"code": "SEMANTIC_INPUT_UNAVAILABLE", "input": name})
        if reasons:
            excluded.append({"name": manifest.name, "reasons": reasons})
            continue
        candidates.append({
            "manifest": manifest.model_dump(mode="json"),
            "input_candidates": input_candidates,
            "execution_mode": ("agent_executable" if manifest.agent_executable else "advisory") if manifest.implementation == "skill" else "executable",
            "required_inputs": [name for name, role in manifest.roles.items() if role.required]
                + [name for name, param in manifest.parameters.items() if param.required and param.default is None],
            "conditional_capabilities": manifest.provides_when,
            "description_available": bool(manifest.description.strip() and manifest.description != manifest.name),
        })
    return {
        "status": "candidates" if candidates else "no_available_candidate",
        "candidates": candidates, "excluded": excluded,
        "capabilities": capabilities,
        "unknown_capabilities": sorted(set(goal.required_capabilities) - set(capabilities)) if goal else [],
        "semantic_meaning_verified": False,
        "guidance": "Query Skills require agent execution through recorded queries; advisory-only Skills remain guidance. Read describe_method for the exact contract. "
            "Compare descriptions with the question; candidates are not a recommendation. "
            "Copy capability names only when their documented meaning matches the question; an empty "
            "capability list makes no assertion about analytical purpose. Input candidates check types, "
            "not variable roles or joins. Ask about ambiguous outcomes, groups, periods or contrasts. "
            "Inspect conditional_capabilities and configure the selected Method. Normal execution still "
            "checks inputs, scope, permissions, budgets and data. If none fits, report the unsupported "
            "part; do not substitute an easier question.",
    }
