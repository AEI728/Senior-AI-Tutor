from uuid import uuid4
from app.db import Practice, Turn


def test_builtin_shares_are_labelled_playable_and_interactive(http):
    shares = http.get("/api/v1/community/works?mine=false&examples=true").json()["items"]
    assert len(shares) >= 4
    assert all(w["is_example"] and not w["is_mine"] and w["video_available"] for w in shares)
    first = shares[0]["id"]
    video = http.get("/api/v1/community/examples/" + first + "/video")
    assert video.status_code == 200 and video.content[4:8] == b"ftyp"
    target = "/api/v1/community/threads/example:" + first
    assert http.put(target + "/reaction", json={"liked": True, "saved": True}).json()["likes"] == 1
    assert http.get("/api/v1/community/works?mine=true&examples=true").json()["items"] == []
    http.headers.pop("Authorization")
    assert http.get("/api/v1/community/examples/" + first + "/video").status_code == 401


def test_voice_coach_needs_no_course_and_is_idempotent(http, db):
    body = {
        "agent_role": "companion",
        "client_request_id": str(uuid4()),
        "message": "我想练习写字，现在拿好笔了",
        "ui_context": {"page": "practice"},
    }
    first = http.post("/api/v1/voice/coach", json=body)
    assert first.status_code == 200
    assert first.json()["intent"] == "VOICE_COACH" and first.json()["reply"]["id"]
    assert http.post("/api/v1/voice/coach", json=body).json()["reply"]["id"] == first.json()["reply"]["id"]
    assert db.query(Practice).count() == 0 and db.query(Turn).count() == 1
    assert http.post("/api/v1/voice/coach", json={**body, "message": "换个问题"}).status_code == 409
