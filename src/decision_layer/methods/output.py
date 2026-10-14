"""Renderer-neutral convenience results on the canonical MethodOutput contract."""
import math
from ..i18n import _
from ..core.models import Artifact, ArtifactColumn
from .base import MethodOutput
from .context import Refused


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Result values must be finite")
        return value
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("Result object keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        return _json_value(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise ValueError("Result contains a non-serializable value")


class Table(MethodOutput):
    artifact_type = "table"

    def __init__(self, rows, *, title=None, warnings=None, validation=None, runtime=None,
                 columns=None):
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise ValueError("Table requires a list of row objects")
        super().__init__(primary=Artifact(type=self.artifact_type, title=title, data=_json_value(rows),
                                         columns=columns or []),
                         warnings=warnings, validation=validation, runtime=runtime)

    @classmethod
    def from_dataset(cls, data, *, require_non_empty=False, **kwargs):
        rows = data.records()
        if require_non_empty and not rows:
            raise Refused(_("No observations in the selected scope"))
        source_columns = {column.ref: column for column in data.dataset.columns}
        columns = [ArtifactColumn(
            name=name, ref=ref,
            role="entity" if group == "unit" else source_columns[ref].role,
            granularity=data.dataset.spec.time.granularity if group == "time" else source_columns[ref].granularity,
        ) for group, pairs in data.roles.items() for name, ref in pairs]
        return cls(rows, columns=columns, **kwargs)


class Estimate(MethodOutput):
    artifact_type = "estimate"

    def __init__(self, value, *, details=None, title=None, warnings=None, validation=None, runtime=None):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("Estimate requires one finite numeric value")
        if details and "value" in details and details["value"] != value:
            raise ValueError("Estimate details must not override the primary value")
        super().__init__(primary=Artifact(type="estimate", title=title,
                         data=_json_value({"value": value, **(details or {})})),
                         warnings=warnings, validation=validation, runtime=runtime)


class TimeSeries(MethodOutput):
    """Compatibility output for existing Methods; new Methods return Table."""
    artifact_type = "time_series"

    @classmethod
    def from_dataset(cls, data, *, require_non_empty=False, warnings=None, title=None):
        rows = data.records()
        if require_non_empty and not rows:
            raise Refused(_("No observations in the selected scope"))
        measures = [(name, ref) for pairs in data.roles.values() for name, ref in pairs
                    if ref in data.dataset.spec.measures]
        if not measures or "time" not in data.roles:
            raise ValueError("TimeSeries requires a measure and time bucket")
        payload = {"rows": rows, "metric": measures[0][0], "metric_ref": measures[0][1],
                   "related": [name for name, ref in measures[1:]], "time_key": data.column("time"),
                   "granularity": data.dataset.spec.time.granularity}
        return cls(primary=Artifact(type="time_series", title=title, data=_json_value(payload)), warnings=warnings)
