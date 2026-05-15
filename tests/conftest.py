import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def settings_env(pg_dsn: str):
    os.environ["DATABASE_URL"] = pg_dsn
    os.environ["SESSION_SECRET"] = "x" * 40
    os.environ["SESSION_COOKIE_SECURE"] = "false"
    # Reset the lru_cache so a new Settings reads the just-set env.
    from tape_service.settings import get_settings
    get_settings.cache_clear()
    yield


@pytest.fixture(scope="session")
def app(settings_env):
    from tape_service.main import create_app
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c
