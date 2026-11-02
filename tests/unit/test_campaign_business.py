import importlib.util
from pathlib import Path

import pandas as pd
import pytest


spec = importlib.util.spec_from_file_location("business_method", Path(__file__).parents[2] /
    "examples/complete-journey/evals/reuse-project/methods/campaign_business/method.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cohort_spec = importlib.util.spec_from_file_location("cohort_method", Path(__file__).parents[2] /
    "examples/complete-journey/evals/reuse-project/methods/campaign_cohort/method.py")
cohort = importlib.util.module_from_spec(cohort_spec)
cohort_spec.loader.exec_module(cohort)


def test_campaign_guard_rejects_multiple_campaigns():
    with pytest.raises(ValueError, match="exactly one campaign"):
        module.check_campaign(pd.DataFrame({"campaign": ["7", "8"]}))


def test_campaign_guard_rejects_missing_group_or_small_group():
    with pytest.raises(ValueError, match="Both"):
        module.check_groups(pd.DataFrame({"target": [1] * 60}), "target")
    with pytest.raises(ValueError, match="30 observations"):
        module.check_groups(pd.DataFrame({"target": [0] * 29 + [1] * 40}), "target")


def test_campaign_method_retains_group_statistics_and_association_limit():
    data = pd.DataFrame({"entity_id": range(80), "campaign": ["7"] * 80,
                         "target": [0, 1] * 40, "prior_sales": list(range(80)),
                         "prior_frequency": [(n * n) % 13 for n in range(80)]})
    data["outcome"] = 5 + 3 * data["target"] + 2 * data["prior_sales"] + data["prior_frequency"]
    module.check_campaign(data)
    module.check_groups(data, "target")
    result = module.compare_campaign(data, "outcome", "target", ["prior_sales", "prior_frequency"])
    assert result["value"] == pytest.approx(3)
    assert [group["households"] for group in result["groups"]] == [40, 40]
    assert result["campaign"] == "7" and result["causal_claim"] == "not_established"


def test_cohort_retains_missingness_and_other_campaigns():
    data = pd.DataFrame({"campaign": ["7", "7"], "target": [0, 1], "outcome": [4, 7],
                         "sales": [2, 5], "freq": [1, 2], "age": [None, "A"],
                         "income": [None, None], "composition": ["B", "C"], "overlaps": [0, 2]})
    rows = cohort.summarize_cohort(data, "outcome", "target", ["sales", "freq"],
                                   "age", "income", "composition", "overlaps")
    assert rows[0]["age_missing"] == 1 and rows[1]["age_missing"] == 0
    assert rows[0]["income_missing"] == rows[1]["income_missing"] == 1
    assert rows[0]["other_campaigns_targeted"] == 0 and rows[1]["other_campaigns_targeted"] == 1
