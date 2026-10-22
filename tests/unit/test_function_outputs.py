"""Ordinary return values keep their shape, details and explicit overrides."""

import pytest

from decision_layer.methods.function.execution import adapt_result


@pytest.mark.parametrize(
    "value, artifact_type, data",
    [
        ([{"group": "A", "value": 30}], "table", [{"group": "A", "value": 30}]),
        ([], "table", []),
        ({"count": 200}, "table", [{"count": 200}]),
        ({"value": "50"}, "table", [{"value": "50"}]),
        ({"value": True}, "table", [{"value": True}]),
        ({"value": None}, "table", [{"value": None}]),
        (0, "estimate", {"value": 0}),
        (50.0, "estimate", {"value": 50.0}),
        ({"value": 0, "count": 200}, "estimate", {"value": 0, "count": 200}),
        (
            {
                "value": 50.0,
                "coefficients": {"treatment": 50.0},
                "causal_claim": "not_established",
            },
            "estimate",
            {
                "value": 50.0,
                "coefficients": {"treatment": 50.0},
                "causal_claim": "not_established",
            },
        ),
    ],
)
def test_auto_adapts_ordinary_returns_without_losing_details(
    value, artifact_type, data
):
    result = adapt_result(value, "auto")
    assert result.primary.type == artifact_type
    assert result.primary.data == data


def test_dataframe_with_value_column_remains_a_table():
    pd = pytest.importorskip("pandas")
    rows = [{"group": "A", "value": 30}]
    result = adapt_result(pd.DataFrame(rows), "auto")
    assert result.primary.type == "table"
    assert result.primary.data == rows


@pytest.mark.parametrize("output", ["table", "estimate"])
def test_explicit_output_overrides_dictionary_inference(output):
    payload = {"value": 50, "n_observations": 200}
    result = adapt_result(payload, output)
    assert result.primary.type == output
    assert result.primary.data == ([payload] if output == "table" else payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize("output", ["auto", "table", "estimate"])
def test_dictionary_inference_does_not_accept_non_finite_results(value, output):
    with pytest.raises(ValueError):
        adapt_result({"value": value, "count": 200}, output)


def test_non_finite_details_are_still_rejected():
    with pytest.raises(ValueError, match="finite"):
        adapt_result({"value": 50, "r_squared": float("nan")}, "auto")
