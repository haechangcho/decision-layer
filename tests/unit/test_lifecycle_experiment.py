import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm


def load(name):
    path = Path(__file__).parents[2] / "examples/complete-journey/evals" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_pairs_and_questions_do_not_teach_analysis():
    module = load("lifecycle_experiment")
    cells = module.schedule()
    assert len(cells) == 60
    for phase in (1, 2, 3):
        for slot in range(1, 11):
            pair = [c for c in cells if c["phase"] == phase and c["slot"] == slot]
            assert {c["arm"] for c in pair} == {"B", "C"}
            assert pair[0]["question"] == pair[1]["question"]
            assert "OLS" not in pair[0]["question"]
            assert "100" not in pair[0]["question"]
    assert "prose only" in module.prompt_for("author", "B", 1)
    assert "update and test reusable code" in module.prompt_for("author", "B", 2)
    assert "Do NOT read or print local repository source" in module.prompt_for("author", "C", 1)


def test_costs_include_authoring_repairs_and_missing_usage():
    module = load("lifecycle_analysis")
    rows = [dict(arm="B", kind=k, phase=1, seconds=10, exit_code=0,
                 usage={"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20})
            for k in ("author", "repair", "business", "audit")]
    rows.append(dict(arm="B", kind="business", phase=2, seconds=600, exit_code=-1, usage=None))
    total = module.aggregate(rows)["B"]["total"]
    assert total["seconds"] == 640
    assert total["reported_input_tokens"] == 400
    assert total["reported_uncached_input_tokens"] == 160
    assert total["usage_missing_jobs"] == 1
    assert total["failed_processes"] == 1


def test_independent_hc3_matches_library_on_heteroskedastic_fixture():
    module = load("lifecycle_analysis")
    rng = np.random.default_rng(128)
    n = 200
    frame = pd.DataFrame({"targeted": np.tile([0, 1], n // 2), "pre_sales_30d": rng.uniform(1, 100, n),
                          "pre_baskets_30d": rng.integers(1, 20, n), "overlapping_campaigns": 0,
                          "age_code": None, "income_code": None, "composition_code": None})
    frame["post_sales_30d"] = 4 + 7 * frame.targeted + .8 * frame.pre_sales_30d + rng.normal(size=n) * frame.pre_sales_30d
    reference = module.numeric_reference(frame)
    x = sm.add_constant(frame[["targeted", "pre_sales_30d", "pre_baskets_30d"]])
    fit = sm.OLS(frame.post_sales_30d, x).fit(cov_type="HC3", use_t=False)
    assert reference["target_coefficient"] == pytest.approx(fit.params["targeted"])
    assert reference["hc3_ci95_normal"] == pytest.approx(fit.conf_int().loc["targeted"].tolist())
    assert reference["eligible"] == {"1": True, "2": True, "3": True}


def test_partial_study_cannot_be_published_as_full_result(tmp_path):
    module = load("lifecycle_analysis")
    (tmp_path / "jobs").mkdir()
    (tmp_path / "manual-reviews.json").write_text(json.dumps({}))
    with pytest.raises(ValueError, match="Incomplete phase"):
        module.reviewed_observations(tmp_path)


def test_adapter_sensitivity_excludes_both_members_of_a_pair():
    module = load("lifecycle_analysis")
    rows = [dict(job_id=f"p2-q{slot:02d}-c5-{arm}", kind="business", arm=arm,
                 phase=2, seconds=10, exit_code=0, usage=None)
            for slot in (1, 2) for arm in ("B", "C")]
    reviews = {rows[0]["job_id"]: {"adapter_confounds": ["export error"]}}
    result = module.sensitivity(rows, reviews)
    assert result["adapter_affected_pairs"] == ["p2-q01-c5"]
    assert result["business_excluding_adapter_pairs"]["B"]["jobs"] == 1
    assert result["business_excluding_adapter_pairs"]["C"]["jobs"] == 1
    assert result["isolated_runtime_business_phases_2_3"]["B"]["jobs"] == 2
