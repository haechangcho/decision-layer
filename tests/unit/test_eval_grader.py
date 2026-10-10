import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "evals"))
from run_eval import grade  # noqa: E402

CALLS = [
    {"name": "run_method", "input": {"name": "query.compare"},
     "output": {"status": "success", "primary": {"data": {"change": 0.092699, "current": 9.0623}}}},
    {"name": "start_run", "input": {"recipe": "r1"},
     "output": {"run_id": "x", "steps": [{"method": "query.decompose", "result": {"status": "refused"}}]}},
]


def test_grade_checks():
    s = {"id": "t", "question": "2026년 비교", "must_call": ["query.compare", "recipe:r1"], "expect_status": ["refused"],
         "expect_numbers": [9.06], "must_not_mention": ["원인"]}
    g = grade(s, {"calls": CALLS, "answers": ["반품률은 9.06%로 0.09%p 올랐습니다."]})
    assert g["passed"], g
    g = grade(s, {"calls": CALLS, "answers": ["반품률은 9.06%, 원인은 1.23%p 입니다."]})
    assert not g["checks"]["must_not_mention"] and g["ungrounded_numbers"] == [1.23]


def test_numbers_are_extracted_whole():
    from run_eval import numbers_in
    assert numbers_in('{"a": 87161.879, "b": "1,234.5"} 12,345원') == [87161.879, 1234.5, 12345.0]


def test_display_units_are_grounded():
    from run_eval import grounded
    assert grounded(0.61, [61186940.0]) and grounded(9.06, [0.0906]) and not grounded(0.52, [61186940.0, 102514453.8])


def test_grader_checks_recorded_coverage_not_only_answer_text():
    scenario = {"question": "Sales and forecast", "require_single_run": True,
                "require_run_coverage": True, "expect_goal_statuses": ["unsupported"]}
    calls = [{"name": "start_analysis", "input": {}, "output": {"run_id": "r"}},
             {"name": "complete_run", "input": {"run_id": "r"}, "output": {
                 "status": "completed", "goals": [{"id": "forecast"}],
                 "conclusion": {"goal_outcomes": [{"goal_id": "forecast", "status": "unsupported"}]}}}]
    result = grade(scenario, {"calls": calls, "answers": ["Forecast unsupported"]})
    assert result["passed"]
    calls[-1]["output"]["conclusion"]["goal_outcomes"] = []
    assert not grade(scenario, {"calls": calls, "answers": ["Forecast unsupported"]})["passed"]


def test_recipe_reuse_requires_completed_invocation_and_recorded_selection():
    ref = "recipe://sales@1.0.0"
    scenario = {"question": "Sales", "must_use_recipe": ref}
    output = {"status": "completed", "recipe": ref,
              "recipe_invocation": {"completed": True},
              "recipe_review": [{"recipe": ref, "decision": "selected"}]}
    run = {"calls": [{"name": "complete_run", "input": {}, "output": output}], "answers": ["Sales"]}
    assert grade(scenario, run)["checks"]["recipe_reused"]
    output["recipe_review"] = []
    assert not grade(scenario, run)["checks"]["recipe_reused"]
    output["recipe_review"] = [{"recipe": ref, "decision": "selected"}]
    output["recipe_invocation"]["completed"] = False
    assert not grade(scenario, run)["checks"]["recipe_reused"]
