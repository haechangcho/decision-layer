"""Run from the repository root: python -m examples.methods.patterns.discovery."""
import asyncio
import json

from decision_layer.core.models import AnalysisGoal
from decision_layer.methods import register_builtins, Scope
from .methods import group_metric
from .scenarios import M, GROUP, DATE, FEB
from .teaching_data import example_session


async def demonstrate():
    session = await example_session("by_group")
    register_builtins(session.registry)
    session.register(group_metric)
    all_methods = session.find_methods()
    lookup = session.find_methods(goal=AnalysisGoal(
        id="lookup", description="Show the requested measure by group",
        semantic_refs=[M, GROUP], required_capabilities=["metric_lookup"],
        interpretation="association",
    ))
    # Inspect the custom Method without inventing a result capability tag.
    custom = session.find_methods(names=[group_metric.manifest.name])
    trial = await session.run(group_metric, metric=M, group=GROUP,
                              scope=Scope(FEB, DATE), limit=3)
    report = {
        "registered": len(session.registry.manifests()),
        "available_without_goal": len(all_methods["candidates"]),
        "lookup_candidates": [c["manifest"]["name"] for c in lookup["candidates"]],
        "custom_description": custom["candidates"][0]["manifest"]["description"],
        "rows": trial.result.primary.data,
        "query_attempts": len(trial.attempts),
        "method_version": trial.result.provenance.method,
        "semantic_refs": trial.result.provenance.semantic_refs,
        "question_relevance_verified": False,
    }
    session.close()
    return report


if __name__ == "__main__":
    print(json.dumps(asyncio.run(demonstrate()), indent=2, ensure_ascii=False))
