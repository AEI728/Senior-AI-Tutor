"""Explicit real-provider acceptance for packaged agent skills; isolated test user."""

import argparse
import json
import secrets
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.config import settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    cfg = settings()
    if cfg.llm_provider == "mock":
        raise SystemExit("REAL_PROVIDER_REQUIRED")
    checks = {}
    report = {"provider": cfg.llm_provider, "checks": checks}
    started = time.monotonic()
    with httpx.Client(base_url=f"http://127.0.0.1:{cfg.app_port}", timeout=90) as c:
        authenticated = False
        try:
            auth = c.post("/api/v1/auth/register", json={
                "username": "skill_" + uuid4().hex[:12], "password": secrets.token_urlsafe(28),
            })
            auth.raise_for_status()
            c.headers["Authorization"] = "Bearer " + auth.json()["access_token"]
            authenticated = True
            assets = c.get("/api/v1/agent/skills")
            assets.raise_for_status()
            assert len(assets.json()["skills"]) == 5
            checks["packaged_assets"] = "PASS"

            def turn(message):
                response = c.post("/api/v1/agent/turns", json={
                    "agent_role": "companion", "client_request_id": str(uuid4()),
                    "message": message, "ui_context": {"page": "home"},
                })
                response.raise_for_status()
                value = response.json()
                assert not value.get("mock_mode") and value["state"] != "FAILED", value.get("error_code", "FAILED")
                return value

            opened = turn("打开技能广场")
            assert opened["ui_actions"][0]["payload"]["page"] == "skills"
            checks["model_navigation_plan"] = "PASS"
            joined = turn("把书法加入技能库，再打开第一节课")
            assert joined["ui_actions"][0]["payload"]["course_id"] == "calligraphy-lines"
            assert joined["state"] == "WAITING_UI_ACK"  # No fake browser ACK in API acceptance.
            checks["compound_add_then_open"] = "PASS"
            recommended = turn("推荐一门摄影课程")
            choices = recommended["recommendations"]
            assert 1 <= len(choices) <= 2 and recommended["ui_actions"] == []
            assert "course-recommendation" in recommended["skill_trace"]
            selected = turn("打开第一门")
            assert selected["ui_actions"][0]["payload"]["course_id"] == choices[0]["course_id"]
            checks["real_catalog_recommendation_and_selection"] = "PASS"
            correction = turn("不是这个，我想学摄影")
            assert correction["recovery"]["strategy"] == "confirm_correction"
            assert turn("确认")["state"] == "SUCCEEDED"
            assert [s["skill_id"] for s in c.get("/api/v1/library").json()["items"]] == ["photography"]
            checks["confirmed_correction"] = "PASS"
            chat = turn("你好，今天练习让我心情挺好的。")
            assert chat["reply"]["speech_text"] and "response-generation" in chat["skill_trace"]
            checks["shared_prompt_chat"] = "PASS"
            coach = c.post("/api/v1/voice/coach", json={
                "agent_role": "tutor", "client_request_id": str(uuid4()),
                "message": "我想练习写字，请告诉我先做什么。", "ui_context": {"page": "practice"},
            })
            coach.raise_for_status()
            assert coach.json()["intent"] == "VOICE_COACH" and coach.json()["reply"]["speech_text"]
            checks["shared_prompt_separate_coach"] = "PASS"
            speech = c.post("/api/v1/audio/speech", json={"reply_id": chat["reply"]["id"]})
            speech.raise_for_status()
            assert len(speech.content) > 44
            checks["tts"] = "PASS"
            report["status"] = "PASS"
        except (httpx.HTTPError, AssertionError, KeyError, ValueError) as error:
            report.update(status="FAIL", error_code=getattr(error, "code", type(error).__name__))
        finally:
            if authenticated:
                cleaned = c.request("DELETE", "/api/v1/me/data", json={"confirmation": "DELETE_MY_DATA"})
                checks["test_user_cleanup"] = "PASS" if cleaned.status_code == 204 else "FAIL"
    report["seconds"] = round(time.monotonic() - started, 2)
    output = ROOT / "artifacts/agent-skills-live.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
