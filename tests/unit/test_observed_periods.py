from datetime import date

import pytest

from decision_layer.core.models import Filter
from decision_layer.methods import registry
from decision_layer.validation import builtin as validation
from tests.support.semantic import AMOUNT, CAT, DT, Q3, ctx


@pytest.mark.parametrize("method", ["query.trend", "query.drilldown"])
async def test_step_period_is_used_without_comparison(provider, monkeypatch, method):
    specs = []
    original = provider.execute
    async def execute(spec, credentials, **kwargs):
        specs.append(spec)
        return await original(spec, credentials, **kwargs)
    monkeypatch.setattr(provider, "execute", execute)
    dates = ["2026-07-20", "2026-07-31"]
    bindings = {"metric": AMOUNT, **({"dimensions": [CAT]} if method.endswith("drilldown") else {})}
    result = await registry.run(method, ctx(provider), bindings, {"current": dates})
    assert result.status == "success"
    assert specs and all(spec.time.date_range == tuple(dates) for spec in specs)
    assert result.primary.data["analysis_period"] == {"date_range": dates, "source": "method_parameters"}


@pytest.mark.parametrize("dates", [["2026-06-01", "2026-07-31"], ["2026-99-01", "2026-09-30"]])
async def test_invalid_or_outside_current_period_never_queries(provider, dates):
    from decision_layer.methods import InvalidBinding
    if dates[0] == "2026-99-01":
        with pytest.raises(InvalidBinding):
            await registry.run("query.trend", ctx(provider), {"metric": AMOUNT}, {"current": dates})
        assert provider.calls == 0
        return
    result = await registry.run("query.trend", ctx(provider), {"metric": AMOUNT}, {"current": dates})
    assert result.status == "refused"
    assert provider.calls == 0


async def test_observed_range_does_not_require_a_sample_count(provider):
    provider.catalog.get(AMOUNT).count_measure = None
    provider.orders = [row for row in provider.orders if row[DT] <= "2026-09-11"]
    result = await validation.freshness(ctx(provider), AMOUNT, Q3)
    assert result.status == "warning" and result.code == "DATA_STALE"
    assert result.details["latest"] == "2026-09-11"
    assert provider.calls == 1


async def test_observed_range_respects_branch_filters(provider):
    provider.orders = [row for row in provider.orders if row[CAT] != "A" or row[DT] <= "2026-09-11"]
    context = ctx(provider)
    result = await validation.freshness(context, AMOUNT, Q3, filters=[Filter(member=CAT, operator="equals", values=["A"])])
    assert result.status == "warning" and result.details["latest"] == "2026-09-11"


def test_calendar_end_does_not_claim_data_completeness():
    result = validation.complete_period(Q3, today=date(2026, 10, 1))
    assert result.status == "pass"
    assert "data coverage" in result.message


async def test_unavailable_daily_query_is_unknown_not_pass(provider, monkeypatch):
    from decision_layer.core.errors import CapabilityMissing
    async def unsupported(*args, **kwargs):
        raise CapabilityMissing("Daily grouping unsupported")
    monkeypatch.setattr(provider, "validate_dataset", unsupported)
    result = await validation.freshness(ctx(provider), AMOUNT, Q3)
    assert result.status == "warning" and result.code == "FRESHNESS_UNKNOWN"
