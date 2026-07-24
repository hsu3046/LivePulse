from __future__ import annotations


def create_event(client, title="테스트 행사"):
    response = client.post("/api/events", json={"title": title, "description": "통합 테스트"})
    assert response.status_code == 201
    return response.json()


def create_single_question(client, event_id, text="선호하는 항목은?"):
    response = client.post(
        f"/api/events/{event_id}/questions",
        json={
            "text": text,
            "type": "SINGLE",
            "options": ["선택 A", "선택 B", "선택 C"],
            "chart_type": "BAR",
            "min_label": "",
            "max_label": "",
        },
    )
    assert response.status_code == 201
    return response.json()


def join(client, code):
    response = client.post(f"/api/public/events/{code}/join", json={})
    assert response.status_code == 200
    return response.json()["participant_session_id"]


def test_full_single_choice_flow_and_result_privacy(client):
    event = create_event(client)
    question = create_single_question(client, event["id"])
    assert client.post(f"/api/events/{event['id']}/actions/lobby").status_code == 204

    participant_a = join(client, event["code"])
    participant_b = join(client, event["code"])

    assert client.post(f"/api/questions/{question['id']}/actions/open").status_code == 204

    option_a, option_b = question["options"][:2]
    for participant, option in [(participant_a, option_a), (participant_b, option_b)]:
        response = client.post(
            f"/api/public/questions/{question['id']}/responses",
            json={"participant_session_id": participant, "option_id": option["id"]},
        )
        assert response.status_code == 200

    # 동일 참가자의 답변 변경은 응답 수를 늘리지 않는다.
    response = client.post(
        f"/api/public/questions/{question['id']}/responses",
        json={"participant_session_id": participant_a, "option_id": option_b["id"]},
    )
    assert response.json()["response_count"] == 2

    participant_state = client.get(
        f"/api/public/events/{event['code']}/state",
        params={"participant_session_id": participant_a},
    ).json()
    assert participant_state["stats"] is None
    assert participant_state["my_response"]["option_id"] == option_b["id"]

    presentation_state = client.get(
        f"/api/presentation/{event['presentation_token']}/state"
    ).json()
    assert presentation_state["stats"] is None
    assert presentation_state["current_response_count"] == 2

    assert client.post(f"/api/questions/{question['id']}/actions/close").status_code == 204
    late = client.post(
        f"/api/public/questions/{question['id']}/responses",
        json={"participant_session_id": participant_a, "option_id": option_a["id"]},
    )
    assert late.status_code == 409

    assert client.post(f"/api/questions/{question['id']}/actions/reveal").status_code == 204
    revealed = client.get(
        f"/api/public/events/{event['code']}/state",
        params={"participant_session_id": participant_a},
    ).json()
    assert revealed["stats"]["total"] == 2
    counts = {item["text"]: item["count"] for item in revealed["stats"]["options"]}
    assert counts == {"선택 A": 0, "선택 B": 2, "선택 C": 0}


def test_only_one_question_can_be_open(client):
    event = create_event(client)
    first = create_single_question(client, event["id"], "첫 질문")
    second = create_single_question(client, event["id"], "둘째 질문")

    assert client.post(f"/api/questions/{first['id']}/actions/open").status_code == 204
    conflict = client.post(f"/api/questions/{second['id']}/actions/open")
    assert conflict.status_code == 409
    assert "먼저 마감" in conflict.json()["detail"]


def test_rating_average_and_csv_export(client):
    event = create_event(client, "평점 행사")
    response = client.post(
        f"/api/events/{event['id']}/questions",
        json={
            "text": "만족도는?",
            "type": "RATING",
            "options": [],
            "chart_type": "BAR",
            "min_label": "낮음",
            "max_label": "높음",
        },
    )
    assert response.status_code == 201
    question = response.json()
    participant_a = join(client, event["code"])
    participant_b = join(client, event["code"])
    client.post(f"/api/questions/{question['id']}/actions/open")

    value_to_option = {item["value"]: item["id"] for item in question["options"]}
    for participant, rating in [(participant_a, 3), (participant_b, 5)]:
        assert client.post(
            f"/api/public/questions/{question['id']}/responses",
            json={"participant_session_id": participant, "option_id": value_to_option[rating]},
        ).status_code == 200

    client.post(f"/api/questions/{question['id']}/actions/close")
    client.post(f"/api/questions/{question['id']}/actions/reveal")
    state = client.get(f"/api/events/{event['id']}/state").json()
    assert state["stats"]["average"] == 4.0

    csv_response = client.get(f"/api/events/{event['id']}/export.csv")
    assert csv_response.status_code == 200
    assert csv_response.content.startswith("\ufeff".encode("utf-8"))
    text = csv_response.content.decode("utf-8-sig")
    assert "평점 행사" in text
    assert "만족도는?" in text


def test_websocket_receives_host_snapshot(client):
    event = create_event(client)
    create_single_question(client, event["id"])
    with client.websocket_connect(f"/ws/events/{event['id']}?role=host") as websocket:
        message = websocket.receive_json()
        assert message["type"] == "STATE_SNAPSHOT"
        assert message["state"]["event"]["id"] == event["id"]
        assert len(message["state"]["questions"]) == 1


def test_validation_and_question_edit_lock(client):
    invalid_event = client.post("/api/events", json={"title": "  ", "description": ""})
    assert invalid_event.status_code == 422

    event = create_event(client)
    duplicate = client.post(
        f"/api/events/{event['id']}/questions",
        json={
            "text": "중복 선택지 질문",
            "type": "SINGLE",
            "options": ["같음", "같음"],
            "chart_type": "BAR",
            "min_label": "",
            "max_label": "",
        },
    )
    assert duplicate.status_code == 422

    question = create_single_question(client, event["id"])
    client.post(f"/api/questions/{question['id']}/actions/open")
    locked = client.put(
        f"/api/questions/{question['id']}",
        json={
            "text": "수정 시도",
            "type": "SINGLE",
            "options": ["A", "B"],
            "chart_type": "BAR",
            "min_label": "",
            "max_label": "",
        },
    )
    assert locked.status_code == 409
