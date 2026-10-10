import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def cube_meta():
    return json.loads((FIXTURES / "cube_meta_ecommerce.json").read_text())


@pytest.fixture
def provider(cube_meta):
    from tests.support.semantic import FakeProvider
    return FakeProvider(cube_meta)
