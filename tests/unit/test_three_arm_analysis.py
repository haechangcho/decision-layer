import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "pilot_analysis", Path(__file__).parents[2] / "examples/complete-journey/evals/three_arm_analysis.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def observation(case, arm, status="pass"):
    return {"case_id": case, "condition": arm, "seconds": 10,
            "usage": {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 10},
            "review": dict.fromkeys(analysis.VALIDITY, status)}


def test_unknown_never_counts_as_verified_pass_and_cache_is_not_added_twice():
    rows = [observation("one", arm) for arm in analysis.ARMS]
    rows[-1]["review"]["V2"] = "unknown"
    result = analysis.summarize(rows)
    assert result["arms"]["decision_layer"]["valid"] == 0
    assert result["arms"]["decision_layer"]["unknown"] == 1
    assert result["arms"]["cube"]["input_tokens"] == 100
    assert result["arms"]["cube"]["uncached_input_tokens"] == 40


def test_repetitions_do_not_increase_the_weight_of_a_base_case():
    rows = [observation("one", arm) for arm in analysis.ARMS]
    rows += [observation("two", arm, "fail" if arm == "decision_layer" else "pass")
             for arm in analysis.ARMS for _ in range(3)]
    result = analysis.summarize(rows)
    assert result["case_count"] == 2
    assert result["paired_valid_rate_difference_C_minus_B"] == -0.5


def test_missing_comparison_is_not_silently_dropped():
    rows = [observation("one", arm) for arm in analysis.ARMS]
    rows.append(observation("two", "cube"))
    with pytest.raises(ValueError, match="Missing pair"):
        analysis.summarize(rows)
