import io
import wave
from uuid import uuid4
from sqlalchemy import select
from app.db import Account
from app.auth import local_token


def turn(http, message, rid=None, **context):
    return http.post(
        "/api/v1/agent/turns",
        json={
            "agent_role": "companion",
            "message": message,
            "client_request_id": rid or str(uuid4()),
            "ui_context": {"page": "home", **context},
        },
    )


def test_multiturn_and_generic_navigation(http):
    assert turn(http, "这个我想学").json()["state"] == "WAITING_USER"
    r = turn(http, "摄影").json()
    assert r["intent"] == "ADD_SKILL"
    assert http.get("/api/v1/library").json()["items"][0]["skill_id"] == "photography"
    for phrase, page in [
        ("返回首页", "home"),
        ("打开技能广场", "skills"),
        ("打开设置", "settings"),
        ("看看作品社区", "community"),
    ]:
        r = turn(http, phrase).json()
        a = r["ui_actions"][0]
        assert a["type"] == "OPEN_PAGE" and a["payload"]["page"] == page
        ack = http.post("/api/v1/agent/ui-actions/" + a["id"] + "/ack", json={"result": "applied"}).json()
        assert ack["state"] == "SUCCEEDED"


def test_new_course_navigation(http):
    r = turn(http, "把书法加入，再打开第一课").json()
    assert r["ui_actions"][0]["payload"]["course_id"] == "calligraphy-lines"
    assert http.get("/api/v1/catalog/courses/calligraphy-lines").status_code == 200


def test_accounts_and_review_visibility(http, db):
    credentials = {"username": "test_person", "password": "test-password-unique-123"}
    register = http.post("/api/v1/auth/register", json=credentials)
    assert register.status_code == 201
    assert http.post("/api/v1/auth/register", json=credentials).status_code == 409
    assert (
        http.post("/api/v1/auth/login", json={**credentials, "password": "wrong-password-123"}).status_code
        == 401
    )
    login = http.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    http.headers["Authorization"] = "Bearer " + login.json()["access_token"]
    assert http.get("/api/v1/library").json()["items"] == []
    w = http.post(
        "/api/v1/community/works",
        json={
            "title": "原创练习记录",
            "description": "今天按步骤尝试了横线。",
            "course_id": "calligraphy-lines",
            "publish_confirmation": "SHARE_THIS_WORK",
        },
    )
    assert w.status_code == 201
    wid = w.json()["id"]
    assert http.get("/api/v1/community/works").json()["items"] == []
    assert len(http.get("/api/v1/community/works?mine=true").json()["items"]) == 1
    assert http.post("/api/v1/community/moderation/" + wid, json={"decision": "approve"}).status_code == 403
    admin = db.scalar(select(Account).where(Account.username == "test_person"))
    admin.is_admin = True
    db.commit()
    assert http.post("/api/v1/community/moderation/" + wid, json={"decision": "approve"}).status_code == 200
    http.headers["Authorization"] = "Bearer " + local_token("separate-user")
    assert len(http.get("/api/v1/community/works").json()["items"]) == 1
    assert http.delete("/api/v1/community/works/" + wid).status_code == 404
    assert http.post("/api/v1/community/works/" + wid + "/report").status_code == 204
    assert http.get("/api/v1/community/works").json()["items"] == []


def test_wav_validation_and_video_auth(http):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * 1600)
    r = http.post("/api/v1/audio/transcriptions", files={"file": ("sample.wav", buf.getvalue(), "audio/wav")})
    assert r.status_code == 503 and r.json()["error"]["code"] == "MOCK_AUDIO_NO_REAL_TRANSCRIPTION_USE_TEXT"
    assert http.get("/api/v1/catalog/courses/calligraphy-lines/demo-video").status_code == 200
    http.headers.pop("Authorization")
    assert http.get("/api/v1/catalog/courses/calligraphy-lines/demo-video").status_code == 401


def test_photo_owner_and_mock_boundary(http):
    sid = http.post("/api/v1/practice/sessions", json={"course_id": "calligraphy-lines"}).json()["id"]
    assert (
        http.post(
            "/api/v1/practice/sessions/" + sid + "/photo-feedback",
            files={"file": ("x.png", b"bad", "image/png")},
        ).status_code
        == 503
    )
    http.headers["Authorization"] = "Bearer " + local_token("another-user")
    assert (
        http.post(
            "/api/v1/practice/sessions/" + sid + "/photo-feedback",
            files={"file": ("x.png", b"bad", "image/png")},
        ).status_code
        == 404
    )
