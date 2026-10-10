"""Canonical contracts shared by every surface (API, MCP, Web, SDK).

Mirrors ARCHITECTURE §5–§15. Everything here is
provider-neutral: Cube specifics live in semantic/providers/cube.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ids import SemanticRefStr, VersionedRefStr
from .periods import ExecutionPolicy, PeriodChoice, checked_range
from ..i18n import _

# ── Semantic catalog ────────────────────────────────────────────────────────

SemanticKind = Literal["measure", "dimension", "time_dimension"]
DataType = Literal["number", "string", "boolean", "time"]
# How a measure aggregates — decides which Methods may use it (ADR-022).
MetricKind = Literal["additive", "count", "average", "ratio", "other"]


class SemanticObject(BaseModel):
    ref: SemanticRefStr
    kind: SemanticKind
    data_type: DataType
    title: str
    description: str | None = None
    metric_kind: MetricKind | None = None          # measures only
    # For ratio measures: numerator / denominator refs, only when the provider declares them.
    ratio_parts: tuple[SemanticRefStr, SemanticRefStr] | None = None
    entity: SemanticRefStr | None = None           # primary key of the object's cube (row grain)
    public: bool = True
    dimension_refs: list[SemanticRefStr] = Field(default_factory=list)
    time_dimension: SemanticRefStr | None = None
    count_measure: SemanticRefStr | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)  # provider-native extras, untouched


class ProviderCapabilities(BaseModel):
    aggregate_queries: bool
    entity_grain_queries: bool
    time_dimensions: bool
    compiled_sql: bool
    hierarchies: bool
    max_rows_per_query: int


class SemanticCatalog(BaseModel):
    provider: str
    instance: str
    objects: list[SemanticObject]
    # Optional provider hints (never required by a Method): ordered level refs per hierarchy.
    hierarchies: dict[str, list[SemanticRefStr]] = Field(default_factory=dict)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get(self, ref: str) -> SemanticObject | None:
        return next((o for o in self.objects if o.ref == ref), None)


# ── Dataset planning ────────────────────────────────────────────────────────

FilterOperator = Literal["equals", "notEquals", "gt", "gte", "lt", "lte", "set", "notSet", "contains"]
Granularity = Literal["day", "week", "month", "quarter", "year"]


class Filter(BaseModel):
    member: SemanticRefStr
    operator: FilterOperator
    values: list[str | int | float | bool] = Field(default_factory=list)

    @model_validator(mode="after")
    def _values_required(self) -> "Filter":
        if self.operator not in ("set", "notSet") and not self.values:
            raise ValueError(f"filter {self.operator} needs values")
        return self


class TimeScope(BaseModel):
    dimension: SemanticRefStr
    date_range: tuple[str, str] | None = None      # inclusive 'YYYY-MM-DD'
    granularity: Granularity | None = None


class DatasetSpec(BaseModel):
    """The data shape a Method needs, independent of the provider (ADR-005)."""
    grain: Literal["aggregate", "entity"]
    measures: list[SemanticRefStr] = Field(default_factory=list)
    dimensions: list[SemanticRefStr] = Field(default_factory=list)
    entity: SemanticRefStr | None = None           # required for grain=entity
    time: TimeScope | None = None
    filters: list[Filter] = Field(default_factory=list)
    order: list[tuple[SemanticRefStr, Literal["asc", "desc"]]] = Field(default_factory=list)
    limit_rows: int | None = None

    @model_validator(mode="after")
    def _shape(self) -> "DatasetSpec":
        if self.grain == "entity" and not self.entity:
            raise ValueError("grain=entity needs an entity ref")
        if not self.measures and not self.dimensions and not self.entity:
            raise ValueError("dataset selects nothing")
        return self


class Column(BaseModel):
    ref: SemanticRefStr
    role: Literal["measure", "dimension", "time", "entity"]
    data_type: DataType
    granularity: Granularity | None = None


class QueryProvenance(BaseModel):
    provider: str
    instance: str
    native_query: dict[str, Any]                   # e.g. the Cube REST query actually sent
    compiled_sql: str | None = None
    rows: int
    elapsed_ms: int
    pages: int = 1
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryAttempt(BaseModel):
    spec: DatasetSpec
    step_id: str | None = None
    status: Literal["running", "success", "failed", "interrupted"] = "running"
    error_code: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Dataset(BaseModel):
    spec: DatasetSpec
    columns: list[Column]
    rows: list[list[Any]]
    provenance: list[QueryProvenance]


# ── Methods ─────────────────────────────────────────────────────────────────

class RoleSpec(BaseModel):
    kind: SemanticKind | Literal["entity"]
    data_type: DataType | None = None
    metric_kinds: list[MetricKind] | None = None   # allowed measure kinds
    required: bool = True
    multiple: bool = False
    description: str = ""
    label: str = ""
    default_binding: Literal["primary_metric", "preferred_dimensions", "unit_count"] | None = None
    ui_group: Literal["basic", "options"] = "basic"
    editor_parameter: str | None = None
    exclusive_group: str | None = None  # alternative semantic inputs, shown as one picker


class InputSourcePolicy(BaseModel):
    allowed: list[Literal["literal", "input", "step"]] = Field(default_factory=lambda: ["literal", "input"])
    default: Literal["literal", "previous_result", "parameter_parents", "runtime_input"] = "literal"
    project: Literal["path", "condition", "parents"] = "path"
    parameter: str | None = None


class InputVisibility(BaseModel):
    parameter: str
    equals: str | bool | int | float


class ParamSpec(BaseModel):
    type: Literal["string", "integer", "number", "boolean", "enum", "date_range", "number_list",
                  "drill_path", "ref_list", "group", "ranges"]
    enum: list[str] | None = None
    default: Any = None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    description: str = ""
    ui_group: Literal["basic", "advanced", "options", "hidden"] = "advanced"
    label: str = ""
    meaning: Literal["analysis_scope", "comparison_subject", "comparison_population", "period", "option"] = "option"
    semantic_kind: SemanticKind | None = None
    semantic_role: str | None = None
    source_policy: InputSourcePolicy | None = None
    visible_when: InputVisibility | None = None


ArtifactType = Literal["estimate", "interval", "table", "breakdown_table", "contribution_table",
                       "coefficient_table", "balance", "sample_summary", "time_series", "warning"]
Interpretation = Literal["descriptive", "associational", "causal_conditional"]


class MethodManifest(BaseModel):
    name: str                                      # "query.drilldown"
    version: str
    kind: Literal["query", "stats", "causal"]
    description: str
    roles: dict[str, RoleSpec]
    parameters: dict[str, ParamSpec] = Field(default_factory=dict)
    execution: Literal["semantic_pushdown", "dataframe"]
    requires_capabilities: list[str] = Field(default_factory=list)
    interpretation: Interpretation                 # ADR-019
    outputs: list[ArtifactType]
    provides: list[str] = Field(default_factory=list)
    provides_when: dict[str, list[str]] = Field(default_factory=dict)
    selection_outputs: list[str] = Field(default_factory=list)
    requires_period: bool = False
    label: str = ""

    @model_validator(mode="after")
    def _input_contract(self) -> "MethodManifest":
        if set(self.provides_when) - set(self.provides) or any(
                not names or set(names) - set(self.parameters) for names in self.provides_when.values()):
            raise ValueError("Conditional result capabilities must reference declared capabilities and parameters")
        groups: dict[str, list[RoleSpec]] = {}
        for role in self.roles.values():
            if role.exclusive_group:
                groups.setdefault(role.exclusive_group, []).append(role)
        if any(len(roles) < 2 or any(role.multiple or role.required for role in roles) for roles in groups.values()):
            raise ValueError("exclusive_group requires at least two optional scalar roles")
        for name, role in self.roles.items():
            if role.default_binding == "unit_count" and (role.kind != "measure" or role.multiple):
                raise ValueError(f"{name}: unit_count requires a scalar measure role")
            if role.editor_parameter:
                spec = self.parameters.get(role.editor_parameter)
                if not spec or spec.type != "string" or spec.semantic_role != name or spec.semantic_kind != role.kind:
                    raise ValueError(f"{name}: editor_parameter must name a matching scalar semantic input")
        for name, spec in self.parameters.items():
            if spec.semantic_kind and spec.type not in ("string", "ref_list"):
                raise ValueError(f"{name}: semantic inputs require string or ref_list")
            if spec.semantic_role and spec.semantic_role not in self.roles:
                raise ValueError(f"{name}: semantic_role must name a declared role")
            if spec.visible_when and spec.visible_when.parameter not in self.parameters:
                raise ValueError(f"{name}: visibility must reference a declared parameter")
            policy = spec.source_policy
            if not policy:
                continue
            required_source = {"previous_result": "step", "parameter_parents": "step", "runtime_input": "input", "literal": "literal"}[policy.default]
            if required_source not in policy.allowed:
                raise ValueError(f"{name}: default source must be allowed")
            if "step" in policy.allowed and spec.type != "drill_path":
                raise ValueError(f"{name}: ranked group selections require drill_path")
            if policy.default == "parameter_parents" and (policy.parameter == name or policy.parameter not in self.parameters):
                raise ValueError(f"{name}: parent source must name another parameter")
            if policy.default == "parameter_parents":
                parent = self.parameters[policy.parameter]
                if parent.type != "drill_path" or (parent.source_policy and parent.source_policy.default == "parameter_parents"):
                    raise ValueError(f"{name}: parent source requires a non-dependent group input")
        return self

    def result_capabilities(self, params: dict[str, Any]) -> list[str]:
        return [capability for capability in self.provides if capability not in self.provides_when
                or any(params.get(name) not in (None, False, [], "") for name in self.provides_when[capability])]


# ── Recipes & plans ─────────────────────────────────────────────────────────

class Routing(BaseModel):
    objective: str = Field(default="", max_length=600)
    use_for: list[str] = Field(default_factory=list)
    do_not_use_for: list[str] = Field(default_factory=list)


class SemanticScope(BaseModel):
    primary_metric: SemanticRefStr
    related_metrics: list[SemanticRefStr] = Field(default_factory=list)
    preferred_dimensions: list[SemanticRefStr] = Field(default_factory=list)  # also the default drill order
    required_filters: list[Filter] = Field(default_factory=list)


class Limits(BaseModel):
    max_steps: int = 12
    max_queries: int = 30


class PlanStep(BaseModel):
    id: str | None = None                          # lets later steps reference this one: $steps.<id>.…
    method: str                                    # "query.drilldown"
    method_version: str | None = None              # optional replay pin from a recorded Run
    purpose: str | None = Field(default=None, max_length=240)  # intended question for this step, not evidence
    purpose_context: Literal["procedure", "source_run"] | None = None
    goal_ids: list[str] = Field(default_factory=list)
    exploration: bool = False
    bindings: dict[str, Any] = Field(default_factory=dict)  # refs, or $expressions in Recipes (checked at run)
    params: dict[str, Any] = Field(default_factory=dict)


class MethodParameterPolicy(BaseModel):
    fixed: dict[str, Any] = Field(default_factory=dict)
    runtime_allowed: list[str] | None = None  # None preserves existing Recipes' unrestricted requests


class ValidatorRef(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class RunDefaults(BaseModel):
    date_range: tuple[str, str] | None = None
    time_dimension: SemanticRefStr | None = None
    period: PeriodChoice | None = None

    @model_validator(mode="after")
    def valid_period(self):
        if self.date_range is not None:
            checked_range(self.date_range)
            if self.period is not None and (self.period.mode != "range" or self.period.date_range != self.date_range):
                raise ValueError("period and date_range conflict")
        return self


class Recipe(BaseModel):
    name: str
    version: str
    description: str
    status: Literal["draft", "published"] = "published"  # legacy files remain executable
    origin_runs: list[str] = Field(default_factory=list)  # reviewed source Runs, never execution inputs
    source_question: str | None = None
    default_scope: RunDefaults | None = None
    inputs: dict[str, ParamSpec] = Field(default_factory=dict)
    routing: Routing = Field(default_factory=Routing)
    semantic_scope: SemanticScope
    mode: Literal["pipeline", "investigation"]
    steps: list[PlanStep] = Field(default_factory=list)          # pipeline
    allowed_methods: list[str] = Field(default_factory=list)     # investigation
    method_parameters: dict[str, MethodParameterPolicy] = Field(default_factory=dict)
    limits: Limits = Field(default_factory=Limits)
    validators: list[ValidatorRef] = Field(default_factory=list)
    instructions: str | None = None                # bounded free text; never overrides semantics

    @model_validator(mode="after")
    def _mode(self) -> "Recipe":
        if self.mode == "pipeline" and not self.steps:
            raise ValueError("pipeline recipe needs steps")
        if self.mode == "investigation" and not self.allowed_methods:
            raise ValueError("investigation recipe needs allowed_methods")
        return self


class AnalysisPlan(BaseModel):
    question: str | None = None
    scope: dict[str, Any] = Field(default_factory=dict)          # date_range, time_dimension, filters
    recipe: VersionedRefStr | None = None
    resolved: dict[str, SemanticRefStr] = Field(default_factory=dict)
    steps: list[PlanStep] = Field(default_factory=list)          # grows in investigation mode


# ── Validation, results, runs ───────────────────────────────────────────────

class ValidationResult(BaseModel):
    validator: str
    status: Literal["pass", "warning", "fail"]
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    type: ArtifactType
    title: str | None = None
    data: Any


class Provenance(BaseModel):
    method: VersionedRefStr | None = None
    recipe: VersionedRefStr | None = None
    semantic_refs: list[SemanticRefStr] = Field(default_factory=list)
    queries: list[QueryProvenance] = Field(default_factory=list)
    runtime: dict[str, str] = Field(default_factory=dict)       # decision-layer / library versions


class Result(BaseModel):
    kind: Literal["analysis_result"] = "analysis_result"
    status: Literal["success", "needs_input", "refused", "failed"]
    interpretation: Interpretation | None = None
    provides: list[str] = Field(default_factory=list)
    primary: Artifact | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation: list[ValidationResult] = Field(default_factory=list)
    needs_input: dict[str, Any] | None = None      # question + candidates when status=needs_input
    provenance: Provenance = Field(default_factory=Provenance)
    run_id: str | None = None                      # the stored Run this result belongs to
    step_id: str | None = None
    selections: dict[str, "SelectionOutput"] = Field(default_factory=dict)


class SelectionCondition(BaseModel):
    member: SemanticRefStr
    value: str | float | int | bool | None


class SelectionCandidate(BaseModel):
    path: list[SelectionCondition] = Field(min_length=1)
    score: float = Field(allow_inf_nan=False)


class SelectionOutput(BaseModel):
    """Unrounded, eligible ranked groups; independent of presentation row limits."""
    kind: Literal["ranked_groups"] = "ranked_groups"
    complete: bool
    rank_by: str
    direction: Literal["asc", "desc"]
    candidates: list[SelectionCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ordered(self) -> "SelectionOutput":
        scores = [candidate.score for candidate in self.candidates]
        if scores != sorted(scores, reverse=self.direction == "desc"):
            raise ValueError("Selection candidates must follow the declared ranking order.")
        return self


class StepSelectionSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["step"]
    step_id: str
    output: str = "ranked_groups"
    select: Literal["first"] = "first"
    project: Literal["path", "condition", "parents"] = "path"


class RuntimeInputSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["input"]
    name: str


class CallerInfo(BaseModel):
    subject: str | None = None
    groups: list[str] = Field(default_factory=list)


class ExecutionAuthor(BaseModel):
    """Informational caller-supplied provenance, never an authenticated identity."""
    client_name: str | None = Field(default=None, max_length=160)
    client_version: str | None = Field(default=None, max_length=160)
    client_source: Literal["protocol", "client_reported", "runner"] = "client_reported"
    model_provider: str | None = Field(default=None, max_length=160)
    model_id: str | None = Field(default=None, max_length=160)
    model_revision: str | None = Field(default=None, max_length=160)
    model_source: Literal["client_reported", "runner"] = "client_reported"


class RunFinding(BaseModel):
    text: str = Field(min_length=1, max_length=600, description="One short observation in plain language. Do not repeat settings or list all diagnostics.")
    step_indices: list[int] = Field(default_factory=list, max_length=12, description="Zero-based recorded steps supporting this observation. These links do not verify the text.")


class AnalysisGoal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
    description: str = Field(min_length=1, max_length=400)
    semantic_refs: list[SemanticRefStr] = Field(default_factory=list, max_length=20)
    required_capabilities: list[str] = Field(default_factory=list, max_length=8)
    interpretation: Interpretation = "descriptive"


class GoalOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal_id: str
    status: Literal["supported", "needs_input", "unsupported", "blocked", "inconclusive"]
    step_indices: list[int] = Field(default_factory=list, max_length=12)
    reason: str = Field(default="", max_length=600)
    reason_code: Literal["method_missing", "semantic_missing", "input_missing", "policy_blocked",
                         "data_insufficient", "execution_error", "access_denied"] | None = None


class SemanticRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(min_length=1, max_length=400)
    kind: SemanticKind
    ref: SemanticRefStr | None = None
    data_type: DataType | None = None
    metric_kind: MetricKind | None = None
    needs_entity: bool = False
    needs_time: bool = False


class SemanticModelDraft(BaseModel):
    """Caller-proposed text for external review; never executable by Decision Layer."""
    model_config = ConfigDict(extra="forbid")
    provider: Literal["cube", "dbt"]
    title: str = Field(min_length=1, max_length=160)
    yaml: str = Field(min_length=1, max_length=12000)
    unresolved: list[Annotated[str, Field(min_length=1, max_length=600)]] = Field(default_factory=list, max_length=12)
    basis: list[Annotated[str, Field(min_length=1, max_length=1200)]] = Field(min_length=1, max_length=12)


class RunRemediation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    goal_id: str
    reason: str
    evidence: str
    proposal: str
    requirements: list[SemanticRequirement]
    model_drafts: list[SemanticModelDraft] = Field(default_factory=list, max_length=3)
    related_goal_ids: list[str] = Field(default_factory=list, max_length=12)
    revision: int = 0
    status: Literal["proposed", "confirmed", "dismissed"] = "proposed"
    events: list[dict[str, Any]] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)


class RunRetryLink(BaseModel):
    run_id: str
    remediation_id: str
    remediation_revision: int
    checked_at: datetime
    requirements: list[SemanticRequirement]


class RecipeSelection(BaseModel):
    reason: str = Field(min_length=1, max_length=600)
    goal_ids: list[str] = Field(default_factory=list)


class RecipeReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: VersionedRefStr
    decision: Literal["selected", "skipped"]
    reason: str = Field(min_length=1, max_length=600, pattern=r"\S")


class RecipeInvocation(BaseModel):
    id: str = "recipe_1"
    recipe: VersionedRefStr
    goal_ids: list[str] = Field(default_factory=list)
    step_ids: list[str] = Field(default_factory=list)
    completed: bool = False
    step_id_map: dict[str, str] = Field(default_factory=dict)


class RunConclusion(BaseModel):
    """Caller explanation or explicitly labelled execution summary, not validation."""
    source: Literal["caller", "execution"] = "caller"
    goal_outcomes: list[GoalOutcome] = Field(default_factory=list, max_length=12)
    answer: str = Field(min_length=1, max_length=600, description="Answer the question in one or two plain-language sentences. Include at most one essential number. Put confidence intervals, sample counts, settings and diagnostic detail in step evidence, not this headline.")
    findings: list[RunFinding] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8, description="Short plain-language limits on the conclusion. Avoid internal field names, validator codes and implementation jargon.")


class StepRecord(BaseModel):
    step: PlanStep
    requested_step: PlanStep | None = None
    input_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    method: VersionedRefStr
    result: Result
    started_at: datetime
    finished_at: datetime
    parameter_sources: dict[str, Literal["method_default", "recipe", "recipe_fixed", "request"]] = Field(default_factory=dict)
    author: ExecutionAuthor | None = None
    invocation_id: str | None = None


class RunningJob(BaseModel):
    """Work executing in the background for a run (ADR-030)."""
    kind: Literal["adhoc", "pipeline", "step", "preview"]
    method: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Run(BaseModel):
    id: str
    plan: AnalysisPlan
    origin: Literal["unknown", "python", "api", "web", "mcp"] = "unknown"
    recipe_snapshot: Recipe | None = None          # immutable copy, not a pointer (MVP_PLAN §15)
    goals: list[AnalysisGoal] = Field(default_factory=list, max_length=12)
    remediations: list[RunRemediation] = Field(default_factory=list)
    retry_of: RunRetryLink | None = None
    recipe_selection: RecipeSelection | None = None
    recipe_review: list[RecipeReview] = Field(default_factory=list, max_length=6)
    recipe_candidates: list[dict[str, Any]] = Field(default_factory=list, max_length=6)
    recipe_invocation: RecipeInvocation | None = None
    query_attempts: list[QueryAttempt] = Field(default_factory=list)
    query_attempt_baseline: int | None = Field(default=None, ge=0)
    active_step: PlanStep | None = None
    interactive: bool = False
    preview: bool = False                           # unsaved Recipe snapshot, executed through the same engine
    steps: list[StepRecord] = Field(default_factory=list)
    caller: CallerInfo = Field(default_factory=CallerInfo)      # the owner
    shared_with: list[str] = Field(default_factory=list)        # subjects with read access ("*": any caller)
    status: Literal["open", "completed", "failed"] = "open"
    running: RunningJob | None = None              # set while a job executes; poll until it clears
    error: dict[str, Any] | None = None            # the last job's error (code, message), if it raised
    needs_input: dict[str, Any] | None = None
    pending_execution: dict[str, Any] | None = None
    scope_revision: int = 0
    scope_resolution: dict[str, Any] = Field(default_factory=dict)
    execution_policy: ExecutionPolicy | None = None
    validation: list[ValidationResult] = Field(default_factory=list)  # recipe-level checks at start
    validation_queries: list[QueryProvenance] = Field(default_factory=list)
    summary: str | None = None                     # the caller's conclusion when completing
    conclusion: RunConclusion | None = None
    author: ExecutionAuthor | None = None          # the initiating client, not the owner
    conclusion_author: ExecutionAuthor | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def ensure_conclusion(self) -> Run:
        """Normalize old terminal Runs and give non-narrated execution a truthful summary."""
        if self.conclusion is not None or self.status == "open":
            return self
        successful = sum(record.result.status == "success" for record in self.steps)
        self.conclusion = RunConclusion(source="execution",
            answer=_("{successful} of {total} analysis steps completed successfully.", successful=successful, total=len(self.steps)),
            findings=[RunFinding(text=record.result.primary.title if record.result.status == "success" and record.result.primary and record.result.primary.title
                                else _("Step status: {status}", status=record.result.status), step_indices=[index])
                      for index, record in enumerate(self.steps[:8])])
        return self
