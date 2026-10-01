"""Stable logical identifiers (ARCHITECTURE §4).

    cube://local/orders/total_amount             semantic object (base cube member)
    method://query/drilldown@1.0.0               method + version
    recipe://return-rate-investigation@1.0.0     recipe + version
    run_01J…                                     run / result ids (time-ordered)

Refs are plain strings on the wire; these helpers parse and build them so the
format lives in one place.
"""
from __future__ import annotations

import os
import re
import time
from typing import Annotated

from pydantic import AfterValidator, BaseModel

from .errors import InvalidReference

_SEMANTIC = re.compile(r"^(?P<provider>[a-z][a-z0-9_-]*)://(?P<instance>[A-Za-z0-9_.-]+)/(?P<cube>[A-Za-z0-9_]+)/(?P<member>[A-Za-z0-9_]+)$")
_VERSIONED = re.compile(r"^(?P<kind>method|recipe)://(?P<name>[a-z0-9_./-]+)@(?P<version>\d+\.\d+\.\d+)$")


class SemanticRef(BaseModel, frozen=True):
    provider: str
    instance: str
    cube: str
    member: str

    @classmethod
    def parse(cls, value: str) -> "SemanticRef":
        m = _SEMANTIC.match(value)
        if not m:
            raise InvalidReference(f"not a semantic ref (provider://instance/cube/member): {value!r}")
        return cls(**m.groupdict())

    @classmethod
    def from_member(cls, member: str, instance: str, provider: str = "cube") -> "SemanticRef":
        cube, _sep, name = member.partition(".")
        if not cube or not name:
            raise InvalidReference(f"not a 'cube.member' name: {member!r}")
        return cls(provider=provider, instance=instance, cube=cube, member=name)

    @property
    def member_name(self) -> str:
        """Provider-native name, e.g. 'orders.total_amount'."""
        return f"{self.cube}.{self.member}"

    def __str__(self) -> str:
        return f"{self.provider}://{self.instance}/{self.cube}/{self.member}"


def _check_semantic(value: str) -> str:
    try:
        SemanticRef.parse(value)
    except InvalidReference as e:  # pydantic only converts ValueError into a validation error
        raise ValueError(e.message) from e
    return value


def _check_versioned(value: str) -> str:
    if not _VERSIONED.match(value):
        raise ValueError(f"not a versioned ref (method|recipe://name@x.y.z): {value!r}")
    return value


SemanticRefStr = Annotated[str, AfterValidator(_check_semantic)]
VersionedRefStr = Annotated[str, AfterValidator(_check_versioned)]


def method_ref(name: str, version: str) -> str:
    return f"method://{name.replace('.', '/')}@{version}"


def recipe_ref(name: str, version: str) -> str:
    return f"recipe://{name.replace('_', '-')}@{version}"


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id(prefix: str) -> str:
    """ULID-style id: 48-bit ms timestamp + 80 random bits, Crockford base32, sortable."""
    value = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    chars = []
    for _i in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return f"{prefix}_{''.join(reversed(chars))}"
