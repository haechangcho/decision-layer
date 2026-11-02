from types import SimpleNamespace

import pytest

from decision_layer.methods import Column, DataInput, python_method
from decision_layer.methods.context import Refused
from decision_layer.methods.function.inputs import query_inputs


def calculation(data):
    return data


METHOD = python_method(calculation, name="test.complete", version="1.0.0", inputs={
    "data": DataInput(columns={"metric": Column(source="measure")}, format="records", require_complete=True)
})


@pytest.mark.parametrize("complete", [False, None])
async def test_required_completeness_refuses_unknown_or_limited(complete):
    class Context:
        async def aggregate(self, **kwargs):
            return SimpleNamespace(records=lambda: [{"metric": 2}],
                dataset=SimpleNamespace(provenance=[SimpleNamespace(retrieval_complete=complete)]))

    with pytest.raises(Refused, match="Complete retrieval"):
        await query_inputs(Context(), METHOD.inputs, METHOD.manifest.roles, {"metric": "metric"}, {})
