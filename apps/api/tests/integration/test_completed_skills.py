from app.auth import local_token


def test_complete_persists_and_rejoin_resets_only_completion(http):
    assert http.post("/api/v1/library/calligraphy/complete").status_code == 404
    http.put("/api/v1/library/calligraphy")
    http.put("/api/v1/progress/calligraphy-lines", json={"position_seconds": 12, "current_step": 1})
    assert http.post("/api/v1/library/calligraphy/complete").json()["status"] == "completed"
    assert http.get("/api/v1/library").json()["items"] == []
    assert http.get("/api/v1/library/completed").json()["items"][0]["skill_id"] == "calligraphy"
    assert http.post("/api/v1/library/calligraphy/complete").json()["status"] == "already_completed"
    assert http.get("/api/v1/progress/recent").json()["items"][0]["position_seconds"] == 12
    http.put("/api/v1/library/calligraphy")
    assert http.get("/api/v1/library/completed").json()["items"] == []
    assert len(http.get("/api/v1/library").json()["items"]) == 1


def test_completed_user_isolation_and_erase(http):
    http.put("/api/v1/library/music")
    http.post("/api/v1/library/music/complete")
    own = http.headers["Authorization"]
    http.headers["Authorization"] = "Bearer " + local_token("other-user")
    assert http.get("/api/v1/library/completed").json()["items"] == []
    http.headers["Authorization"] = own
    http.request("DELETE", "/api/v1/me/data", json={"confirmation": "DELETE_MY_DATA"})
    assert http.get("/api/v1/library/completed").json()["items"] == []
