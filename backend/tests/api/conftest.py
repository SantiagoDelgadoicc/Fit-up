"""Cliente HTTP contra una base de datos temporal, con la fecha congelada."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fitup.api.app import create_app
from fitup.api.deps import Settings
from fitup.api.deps import today as today_dep
from helpers_api import SUNDAY


@pytest.fixture
def app(tmp_path):
    application = create_app(
        Settings(db_path=tmp_path / "fitup.db", token=None, require_token=False)
    )
    # La fecha se inyecta tambien en la API: ningun test debe depender del dia
    # en que se ejecute.
    application.dependency_overrides[today_dep] = lambda: SUNDAY
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def secured(tmp_path):
    application = create_app(
        Settings(db_path=tmp_path / "auth.db", token="secreto", require_token=True)
    )
    with TestClient(application) as c:
        yield c
