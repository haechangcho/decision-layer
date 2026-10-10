"""REST test client factory."""
from fastapi.testclient import TestClient
from decision_layer.api.app import create_app
from decision_layer.semantic.providers.cube.provider import CubeProvider
from decision_layer.settings import Settings
from .cube import FakeClient

def client(cube_meta, **settings):
    s = Settings(cube_api_url="http://x", cube_instance="local", cube_api_secret=settings.get("secret"),
                 cube_service_groups=("ecommerce",), database_url="memory", allow_service_credentials=True,
                 recipes_dir=settings.get("recipes_dir"))
    return TestClient(create_app(s, CubeProvider(FakeClient(cube_meta, rows_total=3), "local")))
