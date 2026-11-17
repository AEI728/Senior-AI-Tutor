import io
from PIL import Image
from sqlalchemy import select
from app.db import Account
from app.auth import local_token


def test_work_image_private_review_and_delete(http, db):
    credentials = {"username": "image_owner", "password": "image-test-password-123"}
    token = http.post("/api/v1/auth/register", json=credentials).json()["access_token"]
    http.headers["Authorization"] = "Bearer " + token
    wid = http.post(
        "/api/v1/community/works",
        json={
            "title": "原创照片",
            "description": "自制测试色块，不含人物。",
            "course_id": "phone-composition",
            "publish_confirmation": "SHARE_THIS_WORK",
        },
    ).json()["id"]
    image = io.BytesIO()
    Image.new("RGB", (60, 40), "green").save(image, "PNG")
    assert (
        http.put(
            "/api/v1/community/works/" + wid + "/image",
            files={"file": ("original.png", image.getvalue(), "image/png")},
        ).status_code
        == 200
    )
    assert http.get("/api/v1/community/works/" + wid + "/image").headers["content-type"] == "image/jpeg"
    http.headers["Authorization"] = "Bearer " + local_token("image-viewer")
    assert http.get("/api/v1/community/works/" + wid + "/image").status_code == 404
    account = db.scalar(select(Account).where(Account.username == "image_owner"))
    account.is_admin = True
    db.commit()
    http.headers["Authorization"] = "Bearer " + token
    assert http.post("/api/v1/community/moderation/" + wid, json={"decision": "approve"}).status_code == 200
    http.headers["Authorization"] = "Bearer " + local_token("image-viewer")
    assert http.get("/api/v1/community/works/" + wid + "/image").status_code == 200
    http.headers["Authorization"] = "Bearer " + token
    assert (
        http.request("DELETE", "/api/v1/me/data", json={"confirmation": "DELETE_MY_DATA"}).status_code == 204
    )
    assert http.get("/api/v1/community/works/" + wid + "/image").status_code == 404
