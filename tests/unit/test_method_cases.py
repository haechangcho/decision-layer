"""Every authoring shape has independent canonical query and numerical expectations."""

import importlib.util
import pytest
from tests.support.methods.run import run_scenario
from tests.support.methods.cases import scenarios


@pytest.mark.parametrize("scenario", scenarios(), ids=lambda item: item.name)
async def test_patterns(scenario):
    dependency = {"ols": "statsmodels", "dowhy": "dowhy", "econml": "econml"}.get(
        scenario.name, "pandas" if scenario.pattern in "DEFG" else None
    )
    if dependency and not importlib.util.find_spec(dependency):
        pytest.skip("Install the documented optional Method extra")
    await run_scenario(scenario)
