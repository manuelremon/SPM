from __future__ import annotations

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("SPM_DEBUG", "1")
    monkeypatch.setenv("SPM_SECRET_KEY", "test-secret-key")
    db_path = tmp_path / "spm-test.db"
    monkeypatch.setenv("SPM_DB_PATH", str(db_path))

    import src.backend.config as config_module
    import src.backend.jwt_utils as jwt_utils_module
    import src.backend.auth as auth_module
    import src.backend.app as app_module

    importlib.reload(config_module)
    importlib.reload(jwt_utils_module)
    importlib.reload(auth_module)
    importlib.reload(app_module)

    flask_app = app_module.create_app()
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    with app.test_client() as testing_client:
        yield testing_client
