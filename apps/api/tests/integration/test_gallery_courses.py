from pathlib import Path
from app.auth import local_token


def test_multiple_lessons_have_distinct_content_and_video(http):
    defaults = {
        "home-gardening": "repotting-basics",
        "calligraphy": "calligraphy-lines",
        "photography": "phone-composition",
        "music": "rhythm-basics",
    }
    for skill, first in defaults.items():
        items = http.get("/api/v1/catalog/skills/" + skill + "/courses").json()["items"]
        assert len(items) == 3 and items[0]["id"] == first
        assert len({c["steps"][1]["instruction"] for c in items}) == 3
        for course in items:
            assert http.get("/api/v1/catalog/courses/" + course["id"] + "/demo-video").status_code == 200


def test_thumbnail_preserves_pending_work_privacy(http):
    work = http.post(
        "/api/v1/community/works",
        json={
            "title": "我的练习",
            "description": "今天的记录",
            "course_id": "calligraphy-lines",
            "publish_confirmation": "SHARE_THIS_WORK",
        },
    ).json()
    endpoint = "/api/v1/community/works/" + work["id"]
    data = (Path(__file__).resolve().parents[4] / "media/calligraphy-lines.mp4").read_bytes()
    assert http.put(endpoint + "/video", files={"file": ("clip.mp4", data, "video/mp4")}).status_code == 200
    image = http.get(endpoint + "/thumbnail")
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8")
    assert http.get(endpoint + "/thumbnail").content == image.content
    http.headers["Authorization"] = "Bearer " + local_token("other-user")
    assert http.get(endpoint + "/thumbnail").status_code == 404
