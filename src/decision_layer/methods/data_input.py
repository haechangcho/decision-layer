"""Author-facing data declarations compiled to the shared execution contract."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.models import DataInput as InputContract
from ..core.models import DataType, RoleSpec


class Column(BaseModel):
    """Declare allowed semantic sources and the values a calculation needs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["measure", "dimension"] | list[Literal["measure", "dimension"]]
    dtype: DataType | None = None
    role: Literal["entity_key"] | None = None
    multiple: bool = False
    required: bool = True
    description: str = ""

    @model_validator(mode="after")
    def valid_source(self):
        sources = [self.source] if isinstance(self.source, str) else self.source
        if not sources or len(set(sources)) != len(sources):
            raise ValueError("Column.source must contain distinct allowed sources")
        if self.role == "entity_key" and (
            sources != ["dimension"] or self.multiple or not self.required
        ):
            raise ValueError("An entity_key must be one required dimension")
        return self

    def to_role(self) -> RoleSpec:
        sources = [self.source] if isinstance(self.source, str) else self.source
        return RoleSpec(
            kind="entity" if self.role == "entity_key" else sources[0],
            accepted_kinds=sources if len(sources) > 1 else None,
            data_type=self.dtype,
            multiple=self.multiple,
            required=self.required,
            description=self.description,
        )


class DataInput(InputContract):
    """Describe one function's table; legacy declarations remain supported.

    An entity_key column selects the observation unit through ordinary bindings.
    Matching names become function column arguments at registration time.
    """

    columns: dict[str, Column | RoleSpec] = Field(default_factory=dict)
    grain: Literal["aggregate", "entity"] | None = None

    @model_validator(mode="after")
    def valid_columns(self):
        InputContract.model_validate(self._contract_values())
        return self

    @model_validator(mode="after")
    def valid_grain(self):
        if self.grain is not None and self.entity is not None:
            raise ValueError("Use grain or the legacy entity role, not both")
        if self.grain == "entity" and {"entity", "unit"}.intersection(
            [*self.measures, *self.dimensions, *self.columns]
        ):
            raise ValueError("entity and unit are reserved for the entity grain")
        return self

    def _contract_values(self):
        values = self.model_dump(exclude={"grain", "columns"})
        keys = [
            name
            for name, column in self.columns.items()
            if isinstance(column, Column) and column.role == "entity_key"
        ]
        if len(keys) > 1:
            raise ValueError("Declare only one entity_key per DataInput")
        if keys and (self.grain is not None or self.entity is not None):
            raise ValueError("Use an entity_key column without grain or legacy entity")
        values["entity"] = (
            keys[0] if keys else ("entity" if self.grain == "entity" else self.entity)
        )
        values["columns"] = {
            name: column.to_role() if isinstance(column, Column) else column
            for name, column in self.columns.items()
        }
        return values

    def contract(self, signature, explicit_arguments=()) -> InputContract:
        arguments = list(self.column_args)
        for name, column in self.columns.items():
            if (
                isinstance(column, Column)
                and name in signature.parameters
                and name not in explicit_arguments
            ):
                if name not in arguments:
                    arguments.append(name)
        values = self._contract_values()
        values["column_args"] = arguments
        return InputContract.model_validate(values)
