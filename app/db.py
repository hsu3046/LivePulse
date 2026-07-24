from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal

import psycopg
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "data" / "livepulse.db"
DatabaseDialect = Literal["sqlite", "postgresql"]

POSTGRES_TABLES = {
    "events": 'public."LivePulse_events"',
    "questions": 'public."LivePulse_questions"',
    "options": 'public."LivePulse_options"',
    "participant_sessions": 'public."LivePulse_participant_sessions"',
    "responses": 'public."LivePulse_responses"',
    "event_logs": 'public."LivePulse_event_logs"',
}
_TABLE_PATTERN = re.compile(
    r'(?<![\w"])('
    + "|".join(sorted((re.escape(name) for name in POSTGRES_TABLES), key=len, reverse=True))
    + r')(?![\w"])'
)


class DatabaseConnection:
    """SQLite와 PostgreSQL의 작은 SQL 차이를 한곳에서 처리한다."""

    def __init__(self, raw_connection: Any, dialect: DatabaseDialect) -> None:
        self.raw_connection = raw_connection
        self.dialect = dialect

    def execute(self, statement: str, parameters: tuple[Any, ...] = ()) -> Any:
        query = prepare_sql(statement, self.dialect)
        return self.raw_connection.execute(query, parameters)

    def executescript(self, script: str) -> Any:
        if self.dialect != "sqlite":
            raise RuntimeError("PostgreSQL 스키마는 supabase/migrations로 적용해야 합니다.")
        return self.raw_connection.executescript(script)

    def commit(self) -> None:
        self.raw_connection.commit()

    def rollback(self) -> None:
        self.raw_connection.rollback()

    def close(self) -> None:
        self.raw_connection.close()


def prepare_sql(statement: str, dialect: DatabaseDialect) -> str:
    if dialect == "sqlite":
        return statement

    normalized = statement.strip().upper()
    if normalized == "BEGIN IMMEDIATE":
        return "BEGIN"

    translated = _TABLE_PATTERN.sub(
        lambda match: POSTGRES_TABLES[match.group(1)],
        statement,
    )
    return translated.replace("?", "%s")


def database_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value or None


def database_backend() -> DatabaseDialect:
    return "postgresql" if database_url() else "sqlite"


def database_path() -> Path:
    configured = os.getenv("LIVEPULSE_DB")
    path = Path(configured).expanduser().resolve() if configured else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection() -> Iterator[DatabaseConnection]:
    configured_url = database_url()
    if configured_url:
        raw_connection = psycopg.connect(
            configured_url,
            connect_timeout=10,
            application_name="LivePulse",
            row_factory=dict_row,
            prepare_threshold=None,
        )
        conn = DatabaseConnection(raw_connection, "postgresql")
    else:
        raw_connection = sqlite3.connect(
            database_path(),
            timeout=10,
            check_same_thread=False,
        )
        raw_connection.row_factory = sqlite3.Row
        raw_connection.execute("PRAGMA foreign_keys = ON")
        raw_connection.execute("PRAGMA busy_timeout = 5000")
        conn = DatabaseConnection(raw_connection, "sqlite")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    if database_backend() == "postgresql":
        with connection() as conn:
            row = conn.execute(
                "SELECT to_regclass(?) AS table_name",
                ('public."LivePulse_events"',),
            ).fetchone()
            if not row or row["table_name"] is None:
                raise RuntimeError(
                    "Supabase 스키마가 없습니다. supabase/migrations를 먼저 적용해 주세요."
                )
        return

    schema = """
    PRAGMA journal_mode = WAL;

    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL UNIQUE,
        presentation_token TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'DRAFT'
            CHECK (status IN ('DRAFT', 'LOBBY', 'RUNNING', 'ENDED')),
        display_mode TEXT NOT NULL DEFAULT 'LOBBY'
            CHECK (display_mode IN ('LOBBY', 'WAITING', 'QUESTION', 'QUESTION_CLOSED', 'RESULT', 'ENDED')),
        current_question_id TEXT,
        revision INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        ended_at TEXT
    );

    CREATE TABLE IF NOT EXISTS questions (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('SINGLE', 'RATING')),
        status TEXT NOT NULL DEFAULT 'READY'
            CHECK (status IN ('DRAFT', 'READY', 'OPEN', 'CLOSED', 'REVEALED')),
        position INTEGER NOT NULL,
        chart_type TEXT NOT NULL DEFAULT 'BAR'
            CHECK (chart_type IN ('BAR', 'PIE')),
        min_label TEXT NOT NULL DEFAULT '',
        max_label TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_questions_event_position
        ON questions(event_id, position);

    CREATE TABLE IF NOT EXISTS options (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        text TEXT NOT NULL,
        position INTEGER NOT NULL,
        value INTEGER,
        UNIQUE(question_id, position)
    );

    CREATE TABLE IF NOT EXISTS participant_sessions (
        id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_participants_event
        ON participant_sessions(event_id);

    CREATE TABLE IF NOT EXISTS responses (
        id TEXT PRIMARY KEY,
        question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        participant_session_id TEXT NOT NULL REFERENCES participant_sessions(id) ON DELETE CASCADE,
        option_id TEXT NOT NULL REFERENCES options(id) ON DELETE RESTRICT,
        submitted_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(question_id, participant_session_id)
    );

    CREATE INDEX IF NOT EXISTS idx_responses_question
        ON responses(question_id);

    CREATE TABLE IF NOT EXISTS event_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
        action TEXT NOT NULL,
        payload TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    );
    """
    with connection() as conn:
        conn.executescript(schema)
