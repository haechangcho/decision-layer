"""Execute independent Method cases and serialize canonical test requests."""

from dataclasses import asdict
from decision_layer.methods import Scope

from decision_layer.dev import MethodSession
from tests.support.methods.functions import AUTHORED
from tests.support.methods.cases import verify


async def run_scenario(scenario):
    provider = scenario.provider()
    session = await MethodSession.fixture(provider)
    for implementation in AUTHORED:
        session.register(implementation)
    trial = await session.run(scenario.method, **scenario.arguments)
    verify(scenario, trial)
    provider.assert_consumed()
    return trial


def wire(value):
    if isinstance(value, Scope):
        return wire(asdict(value))
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value
