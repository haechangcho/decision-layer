"""Public Method authoring API and explicit built-in registration."""
from ..core.models import Artifact, DatasetSpec, Filter, MethodManifest, ParamSpec, RoleSpec
from .base import Method, MethodOutput
from .context import ExecutionContext, NeedsInput, Refused, Scope
from .registry import InvalidBinding, MethodRegistry
from .inputs import DateRange, Dimension, Entity, Equality, Measure, TimeDimension
from .authoring import method
from .output import Estimate, Table, TimeSeries
from .calculation import InputTable, calculation
from .python import DataInput, python_method
from .data_input import Column
from .skills import SkillMethod, get_authoring_guide
from .catalog import register_builtins


registry = register_builtins(MethodRegistry())
