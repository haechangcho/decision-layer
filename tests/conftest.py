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


@pytest.fixture
def query_methods(monkeypatch):
    """Explicit test capabilities for Run/API framework contract scenarios."""
    from copy import deepcopy
    from decision_layer.methods import registry
    from tests.support.query_methods import METHODS

    monkeypatch.setattr(registry, "_methods", dict(registry._methods))
    monkeypatch.setattr(registry, "_versions", dict(registry._versions))
    monkeypatch.setattr(registry, "_builtin_defaults", set(registry._builtin_defaults))
    for method in METHODS:
        registry.register(deepcopy(method))
    return registry
