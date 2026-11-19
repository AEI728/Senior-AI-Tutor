from uuid import uuid4
from app.db import Turn


def test_assistant_navigation_and_coach_advice_stay_separate(http, db):
    message = "打开技能广场"
    assistant = http.post("/api/v1/agent/turns", json={
        "agent_role": "companion", "client_request_id": str(uuid4()), "message": message,
        "ui_context": {"page": "practice"},
    }).json()
    assert assistant["ui_actions"][0]["type"] == "OPEN_PAGE"
    coach = http.post("/api/v1/voice/coach", json={
        "agent_role": "tutor", "client_request_id": str(uuid4()), "message": message,
        "ui_context": {"page": "practice"},
    }).json()
    assert coach["intent"] == "VOICE_COACH" and coach["ui_actions"] == []
    assert db.get(Turn, assistant["turn_id"]).agent_role == "companion"
    assert db.get(Turn, coach["turn_id"]).agent_role == "tutor"
    invalid = http.post("/api/v1/agent/turns", json={
        "agent_role": "companion", "client_request_id": str(uuid4()), "message": message,
        "ui_context": {"page": "practice"}, "practice_session_id": "not-a-companion-session",
    })
    assert invalid.status_code == 422
