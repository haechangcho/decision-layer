"""Canonical period resolution and server-owned execution boundaries."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator
from ..i18n import _


def checked_range(value: tuple[str, str] | list[str]) -> tuple[str, str]:
    if len(value) != 2:
        raise ValueError("A period needs a start and end date.")
    start, end = (date.fromisoformat(item) for item in value)
    if (start.isoformat(), end.isoformat()) != tuple(value) or start > end:
        raise ValueError("Use ordered ISO dates (YYYY-MM-DD).")
    return start.isoformat(), end.isoformat()


class PeriodChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["range", "all", "relative", "unresolved"]
    date_range: tuple[str, str] | None = None
    preset: Literal["last_complete_month", "last_n_days"] | None = None
    days: int | None = Field(default=None, ge=1, le=3660)
    timezone: str = "UTC"
    source: Literal["caller", "conversation", "ai_proposal"] = "caller"

    @model_validator(mode="after")
    def validate_choice(self):
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown timezone.") from exc
        if self.mode == "range":
            if self.date_range is None:
                raise ValueError("A range needs dates.")
            checked_range(self.date_range)
        elif self.date_range is not None:
            raise ValueError("Only a range may contain dates.")
        if self.mode == "relative":
            if not self.preset or (self.preset == "last_n_days" and self.days is None):
                raise ValueError("A relative period needs a preset and its required inputs.")
            if self.preset != "last_n_days" and self.days is not None:
                raise ValueError("days only applies to last_n_days.")
        elif self.preset is not None or self.days is not None:
            raise ValueError("Presets only apply to relative periods.")
        return self


class ExecutionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    allow_all: bool = False
    max_period_days: int = Field(default=366, ge=1)
    deadline_seconds: float = Field(default=120, gt=0)
    max_queries: int = Field(default=30, ge=1)
    max_result_rows: int = Field(default=50000, ge=1)
    allow_recipe_extension: bool = True
    default_period: PeriodChoice | None = None

    @property
    def revision(self) -> str:
        return sha256(self.model_dump_json().encode()).hexdigest()[:16]

    def issue(self, choice: PeriodChoice) -> str | None:
        if choice.mode == "unresolved":
            return _("Choose an analysis period or explicitly request all periods.")
        if choice.mode == "all" and not self.allow_all:
            return _("The server does not allow all-period queries. Choose a date range.")
        if choice.date_range:
            start, end = map(date.fromisoformat, choice.date_range)
            if (end - start).days + 1 > self.max_period_days:
                return _("Choose a period of at most {days} days.", days=self.max_period_days)
        return None


def resolve_scope(scope: dict[str, Any], defaults: dict[str, Any] | None,
                  policy: ExecutionPolicy, now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    defaults = defaults or {}
    explicit = scope.get("period") is not None or scope.get("date_range") is not None
    base = {**defaults, **scope}
    if explicit:
        supplied, dates = scope.get("period"), scope.get("date_range")
        choice = PeriodChoice.model_validate(supplied) if supplied is not None else PeriodChoice(mode="range", date_range=dates)
        if dates is not None and (choice.mode != "range" or tuple(dates) != choice.date_range):
            raise ValueError("period and date_range conflict.")
        source = choice.source
    elif defaults.get("period") is not None or defaults.get("date_range") is not None:
        choice = PeriodChoice.model_validate(defaults["period"]) if defaults.get("period") else PeriodChoice(mode="range", date_range=defaults["date_range"])
        source = "recipe_default"
    elif policy.default_period:
        choice, source = policy.default_period, "organization_default"
    else:
        choice, source = PeriodChoice(mode="unresolved"), "unspecified"
    requested = choice.model_dump(mode="json")
    if choice.mode == "unresolved":
        source = "unspecified"
    if choice.mode == "relative":
        today = now.astimezone(ZoneInfo(choice.timezone)).date()
        if choice.preset == "last_complete_month":
            end = today.replace(day=1) - timedelta(days=1)
            start = end.replace(day=1)
        else:
            end = today - timedelta(days=1)
            start = end - timedelta(days=choice.days - 1)
        choice = PeriodChoice(mode="range", date_range=(start.isoformat(), end.isoformat()), timezone=choice.timezone, source=choice.source)
    base["date_range"] = list(choice.date_range) if choice.date_range else None
    base["period"] = choice.model_dump(mode="json")
    return base, {"requested": requested, "source": source, "source_trust": "server" if source in ("recipe_default", "organization_default", "unspecified") else "caller_reported",
                  "resolved_at": now.isoformat(), "policy_revision": policy.revision}
