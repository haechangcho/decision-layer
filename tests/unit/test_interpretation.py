"""Noncausal categories merge for new goals without changing old evidence."""
import pytest
from decision_layer.core.interpretation import supports_interpretation
from decision_layer.core.models import Result


@pytest.mark.parametrize("value", ["association", "descriptive", "associational"])
def test_noncausal_history_retains_labels_and_supports_association(value):
    result = Result(status="success", interpretation=value)
    assert Result.model_validate_json(result.model_dump_json()).interpretation == value
    assert supports_interpretation("association", result.interpretation)
    assert not supports_interpretation("causal_conditional", result.interpretation)


def test_association_rejects_missing_or_causal_interpretation():
    assert not supports_interpretation("association", None)
    assert not supports_interpretation("association", "causal_conditional")
    assert not supports_interpretation("associational", "descriptive")
