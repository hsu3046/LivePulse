from __future__ import annotations

import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin

import qrcode
from fastapi import FastAPI, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import service
from .db import init_db
from .realtime import manager
from .schemas import (
    EventCreate,
    EventUpdate,
    JoinRequest,
    QuestionCreate,
    QuestionUpdate,
    ReorderQuestions,
    ResponseSubmit,
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="LivePulse MVP",
    version="0.1.0",
    description="오프라인 행사용 실시간 질문·응답·결과 시각화 MVP",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(service.DomainError)
async def domain_error_handler(_: Request, exc: service.DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


def _html(name: str) -> FileResponse:
    return FileResponse(STATIC_DIR / name)


@app.get("/", include_in_schema=False)
def root():
    return _html("host.html")


@app.get("/host", include_in_schema=False)
def host_home():
    return _html("host.html")


@app.get("/host/{event_id}", include_in_schema=False)
def host_manage(event_id: str):
    return _html("manage.html")


@app.get("/e/{event_code}", include_in_schema=False)
def participant_page(event_code: str):
    return _html("participant.html")


@app.get("/present/{token}", include_in_schema=False)
def presentation_page(token: str):
    return _html("present.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/events", status_code=201)
def api_create_event(data: EventCreate):
    return service.create_event(data)


@app.get("/api/events")
def api_list_events():
    return service.list_events()


@app.get("/api/events/{event_id}")
def api_get_event(event_id: str):
    return service.get_event(event_id)


@app.get("/api/events/{event_id}/state")
def api_host_state(event_id: str):
    return service.build_snapshot(event_id, "host")


@app.patch("/api/events/{event_id}")
async def api_update_event(event_id: str, data: EventUpdate):
    result = service.update_event(event_id, data)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return result


@app.post("/api/events/{event_id}/questions", status_code=201)
async def api_create_question(event_id: str, data: QuestionCreate):
    result = service.create_question(event_id, data)
    await manager.broadcast_snapshots(event_id, service.build_snapshot, {"host"})
    return result


@app.put("/api/questions/{question_id}")
async def api_update_question(question_id: str, data: QuestionUpdate):
    result = service.update_question(question_id, data)
    await manager.broadcast_snapshots(result["event_id"], service.build_snapshot, {"host"})
    return result


@app.delete("/api/questions/{question_id}", status_code=204)
async def api_delete_question(question_id: str):
    event_id = service.delete_question(question_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot, {"host"})
    return Response(status_code=204)


@app.post("/api/events/{event_id}/questions/reorder", status_code=204)
async def api_reorder_questions(event_id: str, data: ReorderQuestions):
    service.reorder_questions(event_id, data.question_ids)
    await manager.broadcast_snapshots(event_id, service.build_snapshot, {"host"})
    return Response(status_code=204)


@app.post("/api/events/{event_id}/actions/lobby", status_code=204)
async def api_open_lobby(event_id: str):
    service.open_lobby(event_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.post("/api/events/{event_id}/actions/waiting", status_code=204)
async def api_show_waiting(event_id: str):
    service.show_waiting(event_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.post("/api/questions/{question_id}/actions/open", status_code=204)
async def api_open_question(question_id: str):
    event_id = service.open_question(question_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.post("/api/questions/{question_id}/actions/close", status_code=204)
async def api_close_question(question_id: str):
    event_id = service.close_question(question_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.post("/api/questions/{question_id}/actions/reveal", status_code=204)
async def api_reveal_question(question_id: str):
    event_id = service.reveal_question(question_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.post("/api/events/{event_id}/actions/end", status_code=204)
async def api_end_event(event_id: str):
    service.end_event(event_id)
    await manager.broadcast_snapshots(event_id, service.build_snapshot)
    return Response(status_code=204)


@app.get("/api/events/{event_id}/export.csv")
def api_export_csv(event_id: str):
    csv_text = service.export_event_csv(event_id)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="livepulse-responses.csv"'},
    )


@app.get("/api/events/{event_id}/qr.png")
def api_qr_code(event_id: str, request: Request, base_url: str | None = Query(default=None)):
    event = service.get_event(event_id)
    configured_base = os.getenv("PUBLIC_BASE_URL")
    origin = base_url or configured_base or str(request.base_url)
    participant_url = urljoin(origin.rstrip("/") + "/", f"e/{event['code']}")
    image = qrcode.make(participant_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


@app.get("/api/public/events/{event_code}")
def api_public_event(event_code: str):
    # 세션 생성 전 행사 존재 여부를 확인할 때 사용한다.
    with service.connection() as conn:
        event = service._event_by_code_or_raise(conn, event_code)
        return {
            "id": event["id"],
            "code": event["code"],
            "title": event["title"],
            "description": event["description"],
            "status": event["status"],
        }


@app.post("/api/public/events/{event_code}/join")
async def api_join(event_code: str, data: JoinRequest):
    result = service.join_event(event_code, data.participant_session_id)
    await manager.broadcast_snapshots(
        result["event_id"], service.build_snapshot, {"host", "presentation"}
    )
    return result


@app.get("/api/public/events/{event_code}/state")
def api_participant_state(event_code: str, participant_session_id: str):
    with service.connection() as conn:
        event = service._event_by_code_or_raise(conn, event_code)
    service.validate_participant(event["id"], participant_session_id)
    return service.build_snapshot(event["id"], "participant", participant_session_id)


@app.post("/api/public/questions/{question_id}/responses")
async def api_submit_response(question_id: str, data: ResponseSubmit):
    event_id, result = service.submit_response(question_id, data)
    await manager.broadcast_snapshots(
        event_id, service.build_snapshot, {"host", "presentation"}
    )
    return result


@app.get("/api/presentation/{token}/state")
def api_presentation_state(token: str):
    event_id = service.validate_presentation_token(token)
    return service.build_snapshot(event_id, "presentation")


@app.websocket("/ws/events/{event_id}")
async def event_websocket(
    websocket: WebSocket,
    event_id: str,
    role: str = Query(default="participant"),
    participant_id: str | None = Query(default=None),
    presentation_token: str | None = Query(default=None),
):
    try:
        if role == "participant":
            if not participant_id:
                raise service.Forbidden("참가자 세션이 필요합니다.")
            service.validate_participant(event_id, participant_id)
        elif role == "presentation":
            if not presentation_token or service.validate_presentation_token(presentation_token) != event_id:
                raise service.Forbidden("유효한 발표 화면 토큰이 아닙니다.")
        elif role == "host":
            service.get_event(event_id)
        else:
            raise service.Forbidden("지원하지 않는 연결 역할입니다.")
    except service.DomainError:
        await websocket.close(code=4403)
        return

    client = await manager.connect(websocket, event_id, role, participant_id)
    try:
        await manager.send_snapshot(client, service.build_snapshot)
        if role == "participant":
            await manager.broadcast_snapshots(
                event_id, service.build_snapshot, {"host", "presentation"}
            )
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json({"type": "PONG"})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(client)
        if role == "participant":
            await manager.broadcast_snapshots(
                event_id, service.build_snapshot, {"host", "presentation"}
            )
