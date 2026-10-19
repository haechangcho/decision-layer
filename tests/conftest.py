import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def local_test_host(monkeypatch):
    # TestClient's synthetic host is not an approved host in real deployments.
    monkeypatch.setenv("DL_HTTP_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1,::1,api")


@pytest.fixture
def cube_meta():
    return json.loads((FIXTURES / "cube_meta_ecommerce.json").read_text())


@pytest.fixture
def provider(cube_meta):
    from tests.support.semantic import FakeProvider
    return FakeProvider(cube_meta)
