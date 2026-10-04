from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from decision_layer.core.models import Column, Dataset, SemanticCatalog, SemanticObject
from decision_layer.methods.base import InvalidBinding, MethodRegistry
from decision_layer.methods.context import ExecutionContext, Scope
from decision_layer.semantic.credentials import RequestCredentials

spec = spec_from_file_location("contribution_example", Path(__file__).with_name("method.py"))
module = module_from_spec(spec)
spec.loader.exec_module(module)
METRIC = "cube://example/sales/receipts"


class Provider:
    async def execute(self, spec, credentials, **kwargs):
        return Dataset(spec=spec, columns=[Column(ref=METRIC, role="measure", data_type="number")],
                       rows=[[42]], provenance=[])


async def test_template_contract():
    catalog = SemanticCatalog(provider="cube", instance="example", objects=[
        SemanticObject(ref=METRIC, kind="measure", data_type="number", title="Receipts", metric_kind="additive")])
    context = ExecutionContext(provider=Provider(), credentials=RequestCredentials("local"), catalog=catalog, scope=Scope())
    registry = MethodRegistry()
    registry.register(module.MetricSnapshot())
    result = await registry.run("example.metric_snapshot", context, {"metric": METRIC})
    assert result.status == "success" and result.primary.data["value"] == 42
    assert result.provenance.semantic_refs == [METRIC]
    with pytest.raises(InvalidBinding):
        await registry.run("example.metric_snapshot", context, {})
