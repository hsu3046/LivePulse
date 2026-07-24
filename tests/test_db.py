from __future__ import annotations

import pytest

from app.db import POSTGRES_TABLES, prepare_sql


@pytest.mark.parametrize(
    ("logical_name", "physical_name"),
    POSTGRES_TABLES.items(),
)
def test_postgres_sql_uses_livepulse_prefixed_tables(logical_name: str, physical_name: str):
    query = prepare_sql(f"SELECT * FROM {logical_name} WHERE id = ?", "postgresql")

    assert physical_name in query
    assert "id = %s" in query


def test_sqlite_sql_is_unchanged():
    query = "SELECT * FROM events WHERE id = ?"

    assert prepare_sql(query, "sqlite") == query


def test_postgres_converts_sqlite_write_lock():
    assert prepare_sql("BEGIN IMMEDIATE", "postgresql") == "BEGIN"
