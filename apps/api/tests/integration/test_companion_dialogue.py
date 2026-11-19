from uuid import uuid4


def test_companion_can_chat_and_recall_own_recent_dialogue(http, monkeypatch):
    histories = []

    def answer(message, history):
        histories.append(history)
        return "我在呢，您慢慢说。"

    monkeypatch.setattr("app.main.companion_answer", answer)
    for message in ("你好小伴", "我今天心情很好"):
        response = http.post("/api/v1/agent/turns", json={"agent_role":"companion","client_request_id":str(uuid4()),"message":message,"ui_context":{"page":"home"}}).json()
        assert response["intent"] == "CHAT"
        assert response["state"] == "SUCCEEDED"
        assert response["ui_actions"] == []
    assert histories[1][0]["user"] == "你好小伴"
