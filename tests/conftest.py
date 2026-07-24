from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LIVEPULSE_DB", str(tmp_path / "livepulse-test.db"))
    with TestClient(app) as test_client:
        yield test_client
