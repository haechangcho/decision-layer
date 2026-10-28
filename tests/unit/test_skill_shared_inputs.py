"""Markdown-first authoring retains governed execution and explicit old contracts."""
import pytest

from decision_layer.methods.skills import SkillMethod


HEADER = "---\nname: team.review\nversion: 1.0.0\ndescription: Inspect a metric.\n"


def test_query_skill_without_input_boilerplate_has_shared_contract():
    skill = SkillMethod(HEADER + "query_execution: true\n---\n# Inspect the metric\n")
    assert skill.manifest.roles["metric"].required
    assert skill.manifest.roles["metric"].default_binding == "primary_metric"
    assert not skill.manifest.roles["dimensions"].required
    assert skill.manifest.roles["dimensions"].multiple
    assert set(skill.manifest.parameters) == {"filters", "population", "comparison"}
    assert skill.guide.markdown == "# Inspect the metric"
    assert "roles:" not in skill.source_text


@pytest.mark.parametrize("declaration", ["{}", "\n  group: {kind: dimension}"])
def test_explicit_contracts_are_not_replaced(declaration):
    skill = SkillMethod(HEADER + f"query_execution: true\nroles: {declaration}\nparameters: {{}}\n---\nInspect.\n")
    assert set(skill.manifest.roles) == (set() if declaration == "{}" else {"group"})
    assert skill.manifest.parameters == {}


def test_advisory_skill_does_not_gain_query_inputs():
    skill = SkillMethod(HEADER + "---\nRead the definitions.\n")
    assert not skill.manifest.agent_executable
    assert skill.manifest.roles == skill.manifest.parameters == {}
