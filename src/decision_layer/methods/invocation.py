"""Convenient Python/HTTP inputs normalize once into canonical Method bindings."""
from ..i18n import _
from copy import deepcopy
from .registry import InvalidBinding


def invocation_inputs(manifest, *, bindings=None, measures=None, dimensions=None, entity=None):
    result = deepcopy(bindings or {})
    for values, kinds in ((measures or {}, {"measure"}),
                          (dimensions or {}, {"dimension", "time_dimension"})):
        for role, value in values.items():
            spec = manifest.roles.get(role)
            if not spec or not set(spec.accepted_kinds or [spec.kind]).intersection(kinds):
                raise InvalidBinding(_("The semantic input map does not match a declared role"), role=role)
            if role in result:
                raise InvalidBinding(_("Do not supply the same role in bindings and input maps"), role=role)
            result[role] = value
    if entity is not None:
        roles = [name for name, spec in manifest.roles.items() if spec.kind == "entity"]
        if len(roles) != 1 or roles[0] in result:
            raise InvalidBinding(_("entity requires exactly one unbound primary-unit role"))
        result[roles[0]] = entity
    return result
