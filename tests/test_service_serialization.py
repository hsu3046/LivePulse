from __future__ import annotations

from datetime import UTC, datetime

from app.service import json_timestamp


def test_json_timestamp_normalizes_postgres_datetime():
    value = datetime(2026, 7, 24, 12, 30, tzinfo=UTC)

    assert json_timestamp(value) == "2026-07-24T12:30:00+00:00"


def test_json_timestamp_preserves_sqlite_text_and_none():
    assert json_timestamp("2026-07-24T12:30:00+00:00") == "2026-07-24T12:30:00+00:00"
    assert json_timestamp(None) is None
