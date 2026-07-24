from __future__ import annotations

import csv
import io
import json
import secrets
import string
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from .db import connection
from .realtime import manager
from .schemas import EventCreate, EventUpdate, QuestionCreate, QuestionUpdate, ResponseSubmit


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def json_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _generate_code(conn: Any, length: int = 6) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(30):
        code = "".join(secrets.choice(alphabet) for _ in range(length))
        exists = conn.execute("SELECT 1 FROM events WHERE code = ?", (code,)).fetchone()
        if not exists:
            return code
    raise RuntimeError("고유 행사 코드를 생성하지 못했습니다.")


def _lock_clause(
    conn: Any,
    lock: Literal["share", "update"] | None,
) -> str:
    if getattr(conn, "dialect", "sqlite") != "postgresql" or lock is None:
        return ""
    return " FOR SHARE" if lock == "share" else " FOR UPDATE"


def _event_or_raise(
    conn: Any,
    event_id: str,
    lock: Literal["share", "update"] | None = None,
):
    row = conn.execute(
        f"SELECT * FROM events WHERE id = ?{_lock_clause(conn, lock)}",
        (event_id,),
    ).fetchone()
    if not row:
        raise NotFound("행사를 찾을 수 없습니다.")
    return row


def _event_by_code_or_raise(conn: Any, code: str):
    row = conn.execute(
        "SELECT * FROM events WHERE UPPER(code) = UPPER(?)", (code.strip(),)
    ).fetchone()
    if not row:
        raise NotFound("유효하지 않은 행사 코드입니다.")
    return row


def _question_or_raise(
    conn: Any,
    question_id: str,
    lock: Literal["share", "update"] | None = None,
):
    row = conn.execute(
        f"SELECT * FROM questions WHERE id = ?{_lock_clause(conn, lock)}",
        (question_id,),
    ).fetchone()
    if not row:
        raise NotFound("질문을 찾을 수 없습니다.")
    return row


def _touch_event(conn: Any, event_id: str) -> None:
    now = utc_now()
    conn.execute(
        "UPDATE events SET revision = revision + 1, updated_at = ? WHERE id = ?",
        (now, event_id),
    )


def _log(conn: Any, event_id: str, action: str, payload: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO event_logs(event_id, action, payload, created_at) VALUES (?, ?, ?, ?)",
        (event_id, action, json.dumps(payload or {}, ensure_ascii=False), utc_now()),
    )


def _option_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "text": row["text"],
        "position": row["position"],
        "value": row["value"],
    }


def _question_dict(conn: Any, row: Any, include_response_count: bool = False) -> dict[str, Any]:
    options = conn.execute(
        "SELECT * FROM options WHERE question_id = ? ORDER BY position", (row["id"],)
    ).fetchall()
    result: dict[str, Any] = {
        "id": row["id"],
        "event_id": row["event_id"],
        "text": row["text"],
        "type": row["type"],
        "status": row["status"],
        "position": row["position"],
        "chart_type": row["chart_type"],
        "min_label": row["min_label"],
        "max_label": row["max_label"],
        "options": [_option_dict(option) for option in options],
    }
    if include_response_count:
        result["response_count"] = conn.execute(
            "SELECT COUNT(*) AS count FROM responses WHERE question_id = ?", (row["id"],)
        ).fetchone()["count"]
    return result


def _event_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "presentation_token": row["presentation_token"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "display_mode": row["display_mode"],
        "current_question_id": row["current_question_id"],
        "revision": row["revision"],
        "created_at": json_timestamp(row["created_at"]),
        "updated_at": json_timestamp(row["updated_at"]),
        "ended_at": json_timestamp(row["ended_at"]),
    }


def create_event(data: EventCreate) -> dict[str, Any]:
    now = utc_now()
    event_id = new_id("evt")
    token = secrets.token_urlsafe(24)
    with connection() as conn:
        code = _generate_code(conn)
        conn.execute(
            """
            INSERT INTO events(
                id, code, presentation_token, title, description,
                status, display_mode, revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'DRAFT', 'LOBBY', 1, ?, ?)
            """,
            (event_id, code, token, data.title, data.description, now, now),
        )
        _log(conn, event_id, "EVENT_CREATED")
        event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        return _event_dict(event)


def list_events() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute(
            """
            SELECT e.*,
                   (SELECT COUNT(*) FROM questions q WHERE q.event_id = e.id) AS question_count,
                   (SELECT COUNT(*) FROM participant_sessions p WHERE p.event_id = e.id) AS participant_count,
                   (SELECT COUNT(*) FROM responses r
                      JOIN questions q2 ON q2.id = r.question_id
                     WHERE q2.event_id = e.id) AS response_count
              FROM events e
             ORDER BY e.created_at DESC
            """
        ).fetchall()
        result = []
        for row in rows:
            item = _event_dict(row)
            item.update(
                question_count=row["question_count"],
                participant_count=row["participant_count"],
                response_count=row["response_count"],
            )
            result.append(item)
        return result


def get_event(event_id: str) -> dict[str, Any]:
    with connection() as conn:
        event = _event_or_raise(conn, event_id)
        result = _event_dict(event)
        questions = conn.execute(
            "SELECT * FROM questions WHERE event_id = ? ORDER BY position", (event_id,)
        ).fetchall()
        result["questions"] = [
            _question_dict(conn, row, include_response_count=True) for row in questions
        ]
        result["participant_count"] = conn.execute(
            "SELECT COUNT(*) AS count FROM participant_sessions WHERE event_id = ?",
            (event_id,),
        ).fetchone()["count"]
        result["connected_participant_count"] = manager.connected_participants(event_id)
        return result


def update_event(event_id: str, data: EventUpdate) -> dict[str, Any]:
    values = data.model_dump(exclude_unset=True)
    if not values:
        return get_event(event_id)
    with connection() as conn:
        _event_or_raise(conn, event_id)
        sets = ", ".join(f"{key} = ?" for key in values)
        conn.execute(
            f"UPDATE events SET {sets}, updated_at = ?, revision = revision + 1 WHERE id = ?",
            (*values.values(), utc_now(), event_id),
        )
        _log(conn, event_id, "EVENT_UPDATED", values)
    return get_event(event_id)


def create_question(event_id: str, data: QuestionCreate) -> dict[str, Any]:
    question_id = new_id("q")
    now = utc_now()
    with connection() as conn:
        event = _event_or_raise(conn, event_id, lock="update")
        if event["status"] == "ENDED":
            raise Conflict("종료된 행사에는 질문을 추가할 수 없습니다.")
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 AS next_position FROM questions WHERE event_id = ?",
            (event_id,),
        ).fetchone()["next_position"]
        chart_type = "BAR" if data.type == "RATING" else data.chart_type
        conn.execute(
            """
            INSERT INTO questions(
                id, event_id, text, type, status, position, chart_type,
                min_label, max_label, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'READY', ?, ?, ?, ?, ?, ?)
            """,
            (
                question_id,
                event_id,
                data.text,
                data.type,
                position,
                chart_type,
                data.min_label if data.type == "RATING" else "",
                data.max_label if data.type == "RATING" else "",
                now,
                now,
            ),
        )
        if data.type == "RATING":
            option_texts = ["1", "2", "3", "4", "5"]
            option_values = [1, 2, 3, 4, 5]
        else:
            option_texts = data.options
            option_values = [None] * len(option_texts)
        for idx, (text, value) in enumerate(zip(option_texts, option_values), start=1):
            conn.execute(
                "INSERT INTO options(id, question_id, text, position, value) VALUES (?, ?, ?, ?, ?)",
                (new_id("opt"), question_id, text, idx, value),
            )
        _touch_event(conn, event_id)
        _log(conn, event_id, "QUESTION_CREATED", {"question_id": question_id})
        row = _question_or_raise(conn, question_id)
        return _question_dict(conn, row, include_response_count=True)


def update_question(question_id: str, data: QuestionUpdate) -> dict[str, Any]:
    now = utc_now()
    with connection() as conn:
        existing_question = _question_or_raise(conn, question_id)
        _event_or_raise(conn, existing_question["event_id"], lock="update")
        question = _question_or_raise(conn, question_id, lock="update")
        if question["status"] not in {"DRAFT", "READY"}:
            raise Conflict("진행했거나 응답 중인 질문은 수정할 수 없습니다.")
        response_count = conn.execute(
            "SELECT COUNT(*) AS count FROM responses WHERE question_id = ?", (question_id,)
        ).fetchone()["count"]
        if response_count:
            raise Conflict("응답이 존재하는 질문은 수정할 수 없습니다.")
        chart_type = "BAR" if data.type == "RATING" else data.chart_type
        conn.execute(
            """
            UPDATE questions
               SET text = ?, type = ?, chart_type = ?, min_label = ?, max_label = ?, updated_at = ?
             WHERE id = ?
            """,
            (
                data.text,
                data.type,
                chart_type,
                data.min_label if data.type == "RATING" else "",
                data.max_label if data.type == "RATING" else "",
                now,
                question_id,
            ),
        )
        conn.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
        if data.type == "RATING":
            option_texts = ["1", "2", "3", "4", "5"]
            option_values = [1, 2, 3, 4, 5]
        else:
            option_texts = data.options
            option_values = [None] * len(option_texts)
        for idx, (text, value) in enumerate(zip(option_texts, option_values), start=1):
            conn.execute(
                "INSERT INTO options(id, question_id, text, position, value) VALUES (?, ?, ?, ?, ?)",
                (new_id("opt"), question_id, text, idx, value),
            )
        _touch_event(conn, question["event_id"])
        _log(conn, question["event_id"], "QUESTION_UPDATED", {"question_id": question_id})
        updated = _question_or_raise(conn, question_id)
        return _question_dict(conn, updated, include_response_count=True)


def delete_question(question_id: str) -> str:
    with connection() as conn:
        existing_question = _question_or_raise(conn, question_id)
        _event_or_raise(conn, existing_question["event_id"], lock="update")
        question = _question_or_raise(conn, question_id, lock="update")
        if question["status"] not in {"DRAFT", "READY"}:
            raise Conflict("진행한 질문은 삭제할 수 없습니다.")
        event_id = question["event_id"]
        conn.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        remaining = conn.execute(
            "SELECT id FROM questions WHERE event_id = ? ORDER BY position", (event_id,)
        ).fetchall()
        for position, row in enumerate(remaining, start=1):
            conn.execute("UPDATE questions SET position = ? WHERE id = ?", (position, row["id"]))
        _touch_event(conn, event_id)
        _log(conn, event_id, "QUESTION_DELETED", {"question_id": question_id})
        return event_id


def reorder_questions(event_id: str, question_ids: list[str]) -> None:
    with connection() as conn:
        _event_or_raise(conn, event_id, lock="update")
        existing = conn.execute(
            "SELECT id FROM questions WHERE event_id = ? ORDER BY position", (event_id,)
        ).fetchall()
        existing_ids = {row["id"] for row in existing}
        if set(question_ids) != existing_ids or len(question_ids) != len(existing_ids):
            raise Conflict("질문 목록이 행사에 등록된 질문과 일치하지 않습니다.")
        for position, question_id in enumerate(question_ids, start=1):
            conn.execute(
                "UPDATE questions SET position = ?, updated_at = ? WHERE id = ?",
                (position, utc_now(), question_id),
            )
        _touch_event(conn, event_id)
        _log(conn, event_id, "QUESTIONS_REORDERED")


def open_lobby(event_id: str) -> None:
    with connection() as conn:
        event = _event_or_raise(conn, event_id, lock="update")
        if event["status"] == "ENDED":
            raise Conflict("종료된 행사는 다시 열 수 없습니다.")
        status = "LOBBY" if event["status"] == "DRAFT" else event["status"]
        conn.execute(
            "UPDATE events SET status = ?, display_mode = 'LOBBY', revision = revision + 1, updated_at = ? WHERE id = ?",
            (status, utc_now(), event_id),
        )
        _log(conn, event_id, "LOBBY_OPENED")


def show_waiting(event_id: str) -> None:
    with connection() as conn:
        event = _event_or_raise(conn, event_id, lock="update")
        if event["status"] == "ENDED":
            raise Conflict("종료된 행사입니다.")
        conn.execute(
            "UPDATE events SET display_mode = 'WAITING', revision = revision + 1, updated_at = ? WHERE id = ?",
            (utc_now(), event_id),
        )
        _log(conn, event_id, "WAITING_SHOWN")


def open_question(question_id: str) -> str:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_question = _question_or_raise(conn, question_id)
        event = _event_or_raise(conn, existing_question["event_id"], lock="update")
        question = _question_or_raise(conn, question_id, lock="update")
        if event["status"] == "ENDED":
            raise Conflict("종료된 행사에서는 질문을 열 수 없습니다.")
        if question["status"] == "REVEALED":
            raise Conflict("결과가 공개된 질문은 다시 열 수 없습니다.")
        opened = conn.execute(
            "SELECT id FROM questions WHERE event_id = ? AND status = 'OPEN' AND id != ?",
            (event["id"], question_id),
        ).fetchone()
        if opened:
            raise Conflict("현재 진행 중인 질문을 먼저 마감해 주세요.")
        if question["status"] not in {"READY", "CLOSED", "OPEN"}:
            raise Conflict("현재 상태에서는 질문을 열 수 없습니다.")
        conn.execute(
            "UPDATE questions SET status = 'OPEN', updated_at = ? WHERE id = ?",
            (utc_now(), question_id),
        )
        conn.execute(
            """
            UPDATE events
               SET status = 'RUNNING', display_mode = 'QUESTION', current_question_id = ?,
                   revision = revision + 1, updated_at = ?
             WHERE id = ?
            """,
            (question_id, utc_now(), event["id"]),
        )
        _log(conn, event["id"], "QUESTION_OPENED", {"question_id": question_id})
        return event["id"]


def close_question(question_id: str) -> str:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_question = _question_or_raise(conn, question_id)
        event = _event_or_raise(conn, existing_question["event_id"], lock="update")
        question = _question_or_raise(conn, question_id, lock="update")
        if event["current_question_id"] != question_id or question["status"] != "OPEN":
            raise Conflict("현재 응답 중인 질문만 마감할 수 있습니다.")
        conn.execute(
            "UPDATE questions SET status = 'CLOSED', updated_at = ? WHERE id = ?",
            (utc_now(), question_id),
        )
        conn.execute(
            "UPDATE events SET display_mode = 'QUESTION_CLOSED', revision = revision + 1, updated_at = ? WHERE id = ?",
            (utc_now(), event["id"]),
        )
        _log(conn, event["id"], "QUESTION_CLOSED", {"question_id": question_id})
        return event["id"]


def reveal_question(question_id: str) -> str:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_question = _question_or_raise(conn, question_id)
        event = _event_or_raise(conn, existing_question["event_id"], lock="update")
        question = _question_or_raise(conn, question_id, lock="update")
        if event["current_question_id"] != question_id or question["status"] != "CLOSED":
            raise Conflict("마감된 현재 질문의 결과만 공개할 수 있습니다.")
        conn.execute(
            "UPDATE questions SET status = 'REVEALED', updated_at = ? WHERE id = ?",
            (utc_now(), question_id),
        )
        conn.execute(
            "UPDATE events SET display_mode = 'RESULT', revision = revision + 1, updated_at = ? WHERE id = ?",
            (utc_now(), event["id"]),
        )
        _log(conn, event["id"], "RESULT_REVEALED", {"question_id": question_id})
        return event["id"]


def end_event(event_id: str) -> None:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        event = _event_or_raise(conn, event_id, lock="update")
        if event["status"] == "ENDED":
            return
        if event["current_question_id"]:
            conn.execute(
                "UPDATE questions SET status = 'CLOSED', updated_at = ? WHERE id = ? AND status = 'OPEN'",
                (utc_now(), event["current_question_id"]),
            )
        now = utc_now()
        conn.execute(
            """
            UPDATE events
               SET status = 'ENDED', display_mode = 'ENDED', revision = revision + 1,
                   updated_at = ?, ended_at = ?
             WHERE id = ?
            """,
            (now, now, event_id),
        )
        _log(conn, event_id, "EVENT_ENDED")


def join_event(code: str, requested_session_id: str | None = None) -> dict[str, Any]:
    now = utc_now()
    with connection() as conn:
        event = _event_by_code_or_raise(conn, code)
        event_id = event["id"]
        participant_id = None
        if requested_session_id:
            existing = conn.execute(
                "SELECT * FROM participant_sessions WHERE id = ? AND event_id = ?",
                (requested_session_id, event_id),
            ).fetchone()
            if existing:
                participant_id = existing["id"]
                conn.execute(
                    "UPDATE participant_sessions SET last_seen_at = ? WHERE id = ?",
                    (now, participant_id),
                )
        if participant_id is None:
            participant_id = new_id("ps")
            conn.execute(
                "INSERT INTO participant_sessions(id, event_id, created_at, last_seen_at) VALUES (?, ?, ?, ?)",
                (participant_id, event_id, now, now),
            )
            _log(conn, event_id, "PARTICIPANT_JOINED")
    return {
        "participant_session_id": participant_id,
        "event_id": event_id,
        "state": build_snapshot(event_id, "participant", participant_id),
    }


def submit_response(question_id: str, data: ResponseSubmit) -> tuple[str, dict[str, Any]]:
    now = utc_now()
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing_question = _question_or_raise(conn, question_id)
        event = _event_or_raise(conn, existing_question["event_id"], lock="share")
        question = _question_or_raise(conn, question_id, lock="share")
        if question["status"] != "OPEN":
            raise Conflict("이 질문의 응답이 마감되었습니다.")
        if event["status"] != "RUNNING" or event["current_question_id"] != question_id:
            raise Conflict("현재 응답할 수 있는 질문이 아닙니다.")
        participant = conn.execute(
            "SELECT * FROM participant_sessions WHERE id = ? AND event_id = ?",
            (data.participant_session_id, event["id"]),
        ).fetchone()
        if not participant:
            raise Forbidden("유효한 참가자 세션이 아닙니다.")
        option = conn.execute(
            "SELECT * FROM options WHERE id = ? AND question_id = ?",
            (data.option_id, question_id),
        ).fetchone()
        if not option:
            raise Conflict("이 질문에 속하지 않은 선택지입니다.")
        response_id = new_id("resp")
        conn.execute(
            """
            INSERT INTO responses(
                id, question_id, participant_session_id, option_id, submitted_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id, participant_session_id)
            DO UPDATE SET option_id = excluded.option_id, updated_at = excluded.updated_at
            """,
            (
                response_id,
                question_id,
                data.participant_session_id,
                data.option_id,
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE participant_sessions SET last_seen_at = ? WHERE id = ?",
            (now, data.participant_session_id),
        )
        _touch_event(conn, event["id"])
        total = conn.execute(
            "SELECT COUNT(*) AS count FROM responses WHERE question_id = ?", (question_id,)
        ).fetchone()["count"]
        return event["id"], {
            "accepted": True,
            "question_id": question_id,
            "option_id": data.option_id,
            "response_count": total,
        }


def question_stats(conn: Any, question_id: str) -> dict[str, Any]:
    question = _question_or_raise(conn, question_id)
    rows = conn.execute(
        """
        SELECT o.id, o.text, o.position, o.value, COUNT(r.id) AS count
          FROM options o
          LEFT JOIN responses r ON r.option_id = o.id
         WHERE o.question_id = ?
         GROUP BY o.id, o.text, o.position, o.value
         ORDER BY o.position
        """,
        (question_id,),
    ).fetchall()
    total = sum(row["count"] for row in rows)
    options = []
    weighted_sum = 0
    for row in rows:
        count = row["count"]
        percentage = round((count / total * 100), 1) if total else 0.0
        options.append(
            {
                "id": row["id"],
                "text": row["text"],
                "position": row["position"],
                "value": row["value"],
                "count": count,
                "percentage": percentage,
            }
        )
        if row["value"] is not None:
            weighted_sum += row["value"] * count
    average = round(weighted_sum / total, 2) if total and question["type"] == "RATING" else None
    return {"total": total, "options": options, "average": average}


def build_snapshot(event_id: str, role: str, participant_id: str | None = None) -> dict[str, Any]:
    if role not in {"host", "participant", "presentation"}:
        raise Forbidden("지원하지 않는 연결 역할입니다.")
    with connection() as conn:
        event_row = _event_or_raise(conn, event_id)
        event = _event_dict(event_row)
        # 발표/참가자에게는 발표 토큰을 노출하지 않는다.
        if role != "host":
            event.pop("presentation_token", None)
        participant_total = conn.execute(
            "SELECT COUNT(*) AS count FROM participant_sessions WHERE event_id = ?",
            (event_id,),
        ).fetchone()["count"]
        snapshot: dict[str, Any] = {
            "event": event,
            "counts": {
                "participants_total": participant_total,
                "participants_connected": manager.connected_participants(event_id),
            },
            "current_question": None,
            "stats": None,
        }
        if role == "host":
            questions = conn.execute(
                "SELECT * FROM questions WHERE event_id = ? ORDER BY position", (event_id,)
            ).fetchall()
            snapshot["questions"] = [
                _question_dict(conn, row, include_response_count=True) for row in questions
            ]
        current_id = event_row["current_question_id"]
        if current_id:
            question_row = conn.execute(
                "SELECT * FROM questions WHERE id = ? AND event_id = ?", (current_id, event_id)
            ).fetchone()
            if question_row:
                snapshot["current_question"] = _question_dict(
                    conn, question_row, include_response_count=(role == "host")
                )
                if role in {"host", "presentation"}:
                    snapshot["current_response_count"] = conn.execute(
                        "SELECT COUNT(*) AS count FROM responses WHERE question_id = ?",
                        (current_id,),
                    ).fetchone()["count"]
                can_see_stats = role == "host" or (
                    role == "participant" and question_row["status"] == "REVEALED"
                ) or (
                    role == "presentation" and event_row["display_mode"] == "RESULT"
                )
                if can_see_stats:
                    snapshot["stats"] = question_stats(conn, current_id)
                if role == "participant" and participant_id:
                    response = conn.execute(
                        """
                        SELECT r.option_id, r.submitted_at, r.updated_at, o.text AS option_text
                          FROM responses r
                          JOIN options o ON o.id = r.option_id
                         WHERE r.question_id = ? AND r.participant_session_id = ?
                        """,
                        (current_id, participant_id),
                    ).fetchone()
                    if response:
                        serialized_response = dict(response)
                        serialized_response["submitted_at"] = json_timestamp(
                            response["submitted_at"]
                        )
                        serialized_response["updated_at"] = json_timestamp(
                            response["updated_at"]
                        )
                        snapshot["my_response"] = serialized_response
                    else:
                        snapshot["my_response"] = None
                    snapshot["can_answer"] = question_row["status"] == "OPEN"
        if role == "participant" and "my_response" not in snapshot:
            snapshot["my_response"] = None
            snapshot["can_answer"] = False
        return snapshot


def validate_presentation_token(token: str) -> str:
    with connection() as conn:
        row = conn.execute(
            "SELECT id FROM events WHERE presentation_token = ?", (token,)
        ).fetchone()
        if not row:
            raise NotFound("유효하지 않은 발표 화면 주소입니다.")
        return row["id"]


def validate_participant(event_id: str, participant_id: str) -> None:
    with connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM participant_sessions WHERE id = ? AND event_id = ?",
            (participant_id, event_id),
        ).fetchone()
        if not row:
            raise Forbidden("유효하지 않은 참가자 세션입니다.")


def export_event_csv(event_id: str) -> str:
    with connection() as conn:
        event = _event_or_raise(conn, event_id)
        rows = conn.execute(
            """
            SELECT q.position AS question_no, q.text AS question, q.type AS question_type,
                   p.id AS participant_id, o.text AS answer, o.value AS rating,
                   r.submitted_at, r.updated_at
              FROM responses r
              JOIN questions q ON q.id = r.question_id
              JOIN participant_sessions p ON p.id = r.participant_session_id
              JOIN options o ON o.id = r.option_id
             WHERE q.event_id = ?
             ORDER BY q.position, r.submitted_at
            """,
            (event_id,),
        ).fetchall()
        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output)
        writer.writerow(
            [
                "행사명",
                "질문 번호",
                "질문",
                "질문 유형",
                "익명 참가자 ID",
                "답변",
                "평점",
                "최초 제출 시각",
                "최종 수정 시각",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    event["title"],
                    row["question_no"],
                    row["question"],
                    row["question_type"],
                    row["participant_id"],
                    row["answer"],
                    row["rating"] or "",
                    row["submitted_at"],
                    row["updated_at"],
                ]
            )
        return output.getvalue()
