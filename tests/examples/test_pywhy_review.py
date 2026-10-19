"""Numerical contracts and explicit negative controls, not causal validation."""
import pytest
pytest.importorskip("dowhy")
pytest.importorskip("econml")
from decision_layer.methods import Refused
from examples.methods.pywhy_review.experiment import data, run, validate
from examples.methods.pywhy_review.session import run_case


def test_numerical_routes_and_known_wrapper_limitation():
    run()  # Independent truth and population checks live in verify().


@pytest.mark.parametrize("failure", ["unsupported_type", "duplicate", "missing", "nonfinite", "one_arm", "small_arm",
                                     "no_overlap", "same_contrast", "unknown_category", "outside_support", "constant_dose"])
def test_refusals(failure):
    kind = "continuous" if failure in ("outside_support", "constant_dose") else "binary"
    frame = data(kind)
    control, treated = (0.5, 1.5) if kind == "continuous" else (0, 1)
    if failure == "duplicate": frame.loc[1, "unit"] = frame.loc[0, "unit"]
    if failure == "missing": frame.loc[0, "w"] = None
    if failure == "nonfinite": frame.loc[0, "outcome"] = float("inf")
    if failure == "one_arm": frame["treatment"] = 0
    if failure == "small_arm": frame["treatment"] = [1] * 10 + [0] * (len(frame)-10)
    if failure == "no_overlap": frame["w"] = frame.treatment * 100
    if failure == "same_contrast": treated = control
    if failure == "unknown_category": treated = "missing"
    if failure == "outside_support": treated = 100
    if failure == "constant_dose": frame["treatment"] = 1.0
    with pytest.raises(Refused):
        validate(frame, "unsupported" if failure == "unsupported_type" else kind, control, treated)


@pytest.mark.parametrize("kind,truth", [("categorical", 3), ("continuous", 2)])
async def test_same_method_through_canonical_session(kind, truth):
    trial = await run_case(kind)
    assert trial.result.status == "success", trial.result
    assert abs(trial.result.primary.data["value"]-truth) < .15
    assert len(trial.attempts) == 1
    assert trial.result.interpretation == "associational"


async def test_identical_contrast_refuses_before_any_query():
    trial = await run_case(same_contrast=True)
    assert trial.result.status == "refused"
    assert not trial.attempts


async def test_notebook_imports_same_implementation(monkeypatch):
    from pathlib import Path
    from tests.support.notebooks import execute_notebook
    await execute_notebook(Path(__file__).resolve().parents[2] / "docs/tutorials/methods/pywhy_review.ipynb", monkeypatch)
