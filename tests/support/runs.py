"""Run fixtures/helpers independent of test collection."""
from pathlib import Path
from decision_layer.core.models import AnalysisGoal, GoalOutcome, CallerInfo
from decision_layer.recipes.loader import RecipeStore
from decision_layer.runs.engine import RunEngine
from decision_layer.runs.store import MemoryRunStore
from .semantic import Q3, RR

REPO_RECIPES = Path(__file__).parents[1] / "fixtures" / "recipes"
SCOPE = {"date_range": list(Q3)}
ME = CallerInfo(subject="alice")
MCP_GOALS = [AnalysisGoal(id="answer", description="Inspect the requested metric", semantic_refs=[RR])]
MCP_OUTCOMES = [GoalOutcome(goal_id="answer", status="supported", step_indices=[0])]


def engine(provider, store=None, recipes_dir=REPO_RECIPES):
    return RunEngine(provider, RecipeStore(recipes_dir, "cube", "local"), store or MemoryRunStore())


def write_recipe(tmp_path, text):
    (tmp_path / "r.yaml").write_text(text)
    return tmp_path
