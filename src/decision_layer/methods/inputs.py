"""Small typed authoring inputs; references never contain semantic definitions."""
from dataclasses import dataclass
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field
from ..core.ids import SemanticRefStr
from ..core.models import Filter


@dataclass(frozen=True)
class SemanticRole:
    kind: str


Measure = Annotated[str, SemanticRole("measure")]
Dimension = Annotated[str, SemanticRole("dimension")]
TimeDimension = Annotated[str, SemanticRole("time_dimension")]
Entity = Annotated[str, SemanticRole("entity")]
DateRange = Annotated[tuple[str, str], "date_range"]


class Equality(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member: SemanticRefStr
    value: str | int | float | bool

    def as_filter(self) -> Filter:
        return Filter(member=self.member, operator="equals", values=[self.value])


class AnalysisDesign(BaseModel):
    """Authored assumptions, never evidence that identification is valid."""
    model_config = ConfigDict(extra="forbid")
    note: str = Field(min_length=1, max_length=2000)
    pretreatment_covariates: bool | None = None
    treatment_precedes_outcome: bool | None = None
    no_unmeasured_confounding: bool | None = None
    no_interference: bool | None = None
    independent_units: bool | None = None
    parallel_trends: bool | None = None
    no_anticipation: bool | None = None
    pre_period: str | None = Field(default=None, max_length=30)
    post_period: str | None = Field(default=None, max_length=30)


def parameter_refs(kind: str, value) -> list[str]:
    """One visitor shared by registry validation and authoring services."""
    if kind == "condition" and value:
        return [value.member if isinstance(value, Equality) else value["member"]]
    if kind == "filters":
        return [item.member if isinstance(item, Filter) else item["member"] for item in value or []]
    if kind == "drill_path":
        return [item["member"] for item in value or []]
    return []
