"""Practice sessions tolerate the earlier scenario name in an open kernel."""
from dataclasses import replace

import pytest

from examples.methods.patterns import teaching_data
from examples.methods.patterns.scenarios import scenarios


async def test_open_kernel_with_previous_scenario_name(monkeypatch):
    original = next(case for case in scenarios() if case.name == "by_group")
    previous = replace(original, name="drilldown")
    monkeypatch.setattr(teaching_data, "scenarios", lambda: [previous])

    session = await teaching_data.example_session("by_group")
    assert session.catalog.get("cube://practice/observations/value") is not None
    session.close()


async def test_unknown_example_reports_available_names():
    with pytest.raises(ValueError, match="Unknown practice example.*Choose: by_group"):
        await teaching_data.example_session("unknown")
