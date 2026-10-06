"""Request models shared by the REST API and the MCP server."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .core.models import ExecutionAuthor, Filter, Recipe, RunConclusion


class ScopeIn(BaseModel):
    date_range: tuple[str, str] | None = None
    time_dimension: str | None = None
    filters: list[Filter] = Field(default_factory=list)

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


class RecipeSaveRequest(BaseModel):
    recipe: Recipe
    base_version: str | None = None


class RecipePublishRequest(BaseModel):
    base_version: str


class RecipeYamlRequest(BaseModel):
    yaml: str


class RecipePreviewRequest(BaseModel):
    recipe: Recipe
    step_index: int = Field(ge=0)
    scope: ScopeIn = Field(default_factory=ScopeIn)


class RunStepRequest(BaseModel):
    author: ExecutionAuthor | None = None
    id: str | None = None
    method: str
    purpose: str | None = Field(default=None, max_length=240)
    bindings: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class RunCompleteRequest(BaseModel):
    summary: str | None = None
    conclusion: RunConclusion | None = None
    author: ExecutionAuthor | None = None


class RunShareRequest(BaseModel):
    subjects: list[str] = Field(default_factory=list)   # [] = private again
