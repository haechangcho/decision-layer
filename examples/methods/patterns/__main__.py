"""Run one or all independent, non-networked contributor scenarios."""
import argparse
import asyncio
import json
from decision_layer.dev import MethodSession
from decision_layer.methods import register_builtins
from .methods import AUTHORED
from .scenarios import scenarios, verify


async def run_scenario(scenario):
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    register_builtins(session.registry)
    for implementation in AUTHORED:
        session.register(implementation)
    trial = await session.run(scenario.method, **scenario.arguments)
    verify(scenario, trial)
    provider.assert_consumed()
    return trial


async def main(args):
    available = scenarios()
    selected = available if args.all else [item for item in available if item.name == args.case]
    if not selected:
        raise SystemExit("Unknown scenario. Choose: " + ", ".join(item.name for item in available))
    for scenario in selected:
        trial = await run_scenario(scenario)
        print(json.dumps({"case": scenario.name, "pattern": scenario.pattern, "status": trial.result.status,
                          "interpretation": trial.result.interpretation, "queries": len(trial.attempts),
                          "expected": scenario.expected, "result": trial.result.primary.data}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="by_group")
    parser.add_argument("--all", action="store_true")
    asyncio.run(main(parser.parse_args()))
