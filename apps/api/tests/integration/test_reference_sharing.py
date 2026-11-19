from pathlib import Path
from app.auth import local_token
from app.db import FeedComment, FeedReaction, WorkVideo


def test_reactions_comments_ownership_and_erasure(http, db):
    target = "/api/v1/community/threads/course:repotting-basics"
    assert http.get(target).json()["likes"] == 0
    assert http.put(target + "/reaction", json={"liked": True, "saved": True}).json()["likes"] == 1
    assert http.put(target + "/reaction", json={"liked": True, "saved": True}).json()["likes"] == 1
    c = http.post(target + "/comments", json={"body": "今天开始练习"}).json()
    assert http.post(target + "/comments", json={"body": "   "}).status_code == 422
    assert http.get(target).json()["comments"][0]["own"] is True
    original = http.headers["Authorization"]
    http.headers["Authorization"] = "Bearer " + local_token("another-learner")
    assert http.get(target).json()["liked"] is False
    assert http.delete("/api/v1/community/comments/" + c["id"]).status_code == 404
    http.headers["Authorization"] = original
    assert http.request("DELETE", "/api/v1/me/data", json={"confirmation": "DELETE_MY_DATA"}).status_code == 204
    assert db.query(FeedComment).count() == 0
    assert db.query(FeedReaction).count() == 0


def test_video_validation_visibility_and_removal(http, db):
    work = http.post(
        "/api/v1/community/works",
        json={
            "title": "练习",
            "description": "今天的练习",
            "course_id": "repotting-basics",
            "publish_confirmation": "SHARE_THIS_WORK",
        },
    ).json()
    endpoint = "/api/v1/community/works/" + work["id"]
    assert (
        http.put(endpoint + "/video", files={"file": ("fake.mp4", b"invalid-video", "video/mp4")}).status_code
        == 422
    )
    data = (Path(__file__).resolve().parents[4] / "media/repotting-basics.mp4").read_bytes()
    assert (
        http.put(endpoint + "/video", files={"file": ("practice.mp4", data, "video/mp4")}).status_code == 200
    )
    assert http.get(endpoint + "/video").content == data
    assert http.get("/api/v1/community/works?mine=true").json()["items"][0]["video_available"] is True
    original = http.headers["Authorization"]
    http.headers["Authorization"] = "Bearer " + local_token("different-learner")
    assert http.get(endpoint + "/video").status_code == 404
    assert http.get("/api/v1/community/threads/work:" + work["id"]).status_code == 404
    assert http.put(endpoint + "/video", files={"file": ("x.mp4", data, "video/mp4")}).status_code == 404
    http.headers["Authorization"] = original
    assert http.delete(endpoint).status_code == 204
    assert db.query(WorkVideo).count() == 0
