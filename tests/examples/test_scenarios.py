"""Every authoring shape has independent canonical query and numerical expectations."""
import importlib.util
import pytest
from examples.methods.scenarios.__main__ import run_scenario
from examples.methods.scenarios.scenarios import scenarios


@pytest.mark.parametrize("scenario", scenarios(), ids=lambda item: item.name)
async def test_patterns(scenario):
    dependency = {"ols": "statsmodels", "dowhy": "dowhy", "econml": "econml"}.get(scenario.name, "pandas" if scenario.pattern in "DEFG" else None)
    if dependency and not importlib.util.find_spec(dependency):
        pytest.skip("Install the documented optional Method extra")
    await run_scenario(scenario)
