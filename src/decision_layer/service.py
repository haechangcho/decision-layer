"""Request models shared by the REST API and the MCP server."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from .core.periods import PeriodChoice, checked_range

from .core.models import AnalysisGoal, ExecutionAuthor, Filter, Recipe, RecipeReview, RecipeSelection, RunConclusion, SemanticRequirement, SemanticModelDraft


class ScopeIn(BaseModel):
    period: PeriodChoice | None = None
    date_range: tuple[str, str] | None = None
    time_dimension: str | None = None
    filters: list[Filter] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_period(self):
        if self.date_range is not None:
            checked_range(self.date_range)
            if self.period is not None and (self.period.mode != "range" or self.period.date_range != self.date_range):
                raise ValueError("period and date_range conflict")
        return self

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True)


class MethodRunRequest(BaseModel):
    author: ExecutionAuthor | None = None
    question: str | None = None
    bindings: dict[str, str | list[str]] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    scope: ScopeIn = Field(default_factory=ScopeIn)


class RunStartRequest(BaseModel):
    author: ExecutionAuthor | None = None
    recipe: str | None = None                      # name, name@version or recipe://name@version
    question: str | None = None
    scope: ScopeIn = Field(default_factory=ScopeIn)
    goals: list[AnalysisGoal] = Field(default_factory=list, max_length=12)
    recipe_selection: RecipeSelection | None = None
    recipe_review: list[RecipeReview] = Field(default_factory=list, max_length=5)
    interactive: bool = False


class RunUseRecipeRequest(BaseModel):
    recipe: str
    selection: RecipeSelection
    inputs: dict[str, Any] = Field(default_factory=dict)


class RunScopeRequest(BaseModel):
    scope: ScopeIn
    base_revision: int = Field(ge=0)


class RecipeSaveRequest(BaseModel):
    recipe: Recipe
    base_version: str | None = None


class RecipePublishRequest(BaseModel):
    base_version: str


class RunRecipeRequest(BaseModel):
    reviewed: bool = False
    recipe: Recipe | None = None


class RecipeYamlRequest(BaseModel):
    yaml: str


class RecipePreviewRequest(BaseModel):
    recipe: Recipe
    step_index: int = Field(ge=0)
    scope: ScopeIn = Field(default_factory=ScopeIn)


class RecipeConfigureRequest(BaseModel):
    recipe: Recipe
    step_index: int = Field(ge=0)
    reset_parameters: list[str] = Field(default_factory=list)


class RunStepRequest(BaseModel):
    author: ExecutionAuthor | None = None
    id: str | None = None
    method: str
    purpose: str | None = Field(default=None, max_length=240)
    bindings: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    goal_ids: list[str] = Field(default_factory=list)
    exploration: bool = False


class RecipeSearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    goals: list[AnalysisGoal] = Field(default_factory=list, max_length=12)
    inputs: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=5, ge=1, le=20)


class MethodProposalRequest(BaseModel):
    goal_id: str
    title: str = Field(min_length=1, max_length=120)
    public_question: str = Field(min_length=1, max_length=1000)
    expected_result: str = Field(min_length=1, max_length=1000)


class RunCompleteRequest(BaseModel):
    summary: str | None = None
    conclusion: RunConclusion | None = None
    author: ExecutionAuthor | None = None


class RunShareRequest(BaseModel):
    subjects: list[str] = Field(default_factory=list)   # [] = private again


class RemediationCreateRequest(BaseModel):
    model_config = {"extra": "forbid"}
    goal_id: str
    reason: str = Field(min_length=1, max_length=600)
    evidence: str = Field(min_length=1, max_length=1200)
    proposal: str = Field(min_length=1, max_length=600)
    requirements: list[SemanticRequirement] = Field(min_length=1, max_length=12)
    model_drafts: list[SemanticModelDraft] = Field(default_factory=list, max_length=3)
    related_goal_ids: list[str] = Field(default_factory=list, max_length=12)


class RemediationReviewRequest(BaseModel):
    model_config = {"extra": "forbid"}
    base_revision: int = Field(ge=0)
    decision: Literal["confirmed", "dismissed"]
    note: str = Field(min_length=1, max_length=600)
    requirements: list[SemanticRequirement] = Field(min_length=1, max_length=12)


class RemediationCheckRequest(BaseModel):
    base_revision: int = Field(ge=0)


class RemediationRetryRequest(RunStartRequest):
    base_revision: int = Field(ge=0)


class BlockedAnalysisRequest(BaseModel):
    model_config = {"extra": "forbid"}
    run_id: str | None = None
    question: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    goals: list[AnalysisGoal] = Field(min_length=1, max_length=12)
    conclusion: RunConclusion
    semantic_gaps: list[RemediationCreateRequest] = Field(default_factory=list, max_length=12)
    scope: ScopeIn = Field(default_factory=ScopeIn)
    author: ExecutionAuthor | None = None
