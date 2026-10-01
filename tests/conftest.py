import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cube_meta():
    return json.loads((FIXTURES / "cube_meta_ecommerce.json").read_text())


def ref(member: str) -> str:
    cube, name = member.split(".")
    return f"cube://local/{cube}/{name}"
