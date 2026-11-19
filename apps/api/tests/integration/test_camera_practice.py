import io
from types import SimpleNamespace
from PIL import Image
from app.db import Practice


def test_camera_observation_without_course_and_no_progress_change(http, db, monkeypatch):
    captured = []

    def generate(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="请把手上的物品放近一些，我再帮您看看。"))
            ]
        )

    monkeypatch.setattr(
        "app.vision.settings", lambda: SimpleNamespace(llm_provider="deepseek", deepseek_model="vision")
    )
    monkeypatch.setattr(
        "app.vision.deepseek_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=generate))),
    )
    buf = io.BytesIO()
    Image.new("RGB", (100, 100)).save(buf, "JPEG")
    files = [("files", ("frame.jpg", buf.getvalue(), "image/jpeg")) for _ in range(3)]
    r = http.post("/api/v1/camera/feedback", files=files)
    assert r.status_code == 200
    assert r.json()["frame_count"] == 3
    assert r.json()["reply_id"]
    assert r.json()["progress_changed"] is False
    assert db.query(Practice).count() == 0
    assert len(captured[0]["messages"][1]["content"]) == 4
    assert (
        http.post("/api/v1/camera/feedback", files={"files": ("bad.jpg", b"bad", "image/jpeg")}).status_code
        == 422
    )
    http.headers.pop("Authorization")
    assert http.post("/api/v1/camera/feedback", files=files).status_code == 401
