import json
from sqlalchemy import select
from .config import ROOT
from .db import Session, Skill, Course


def seed_one(path):
    payload = json.loads(path.read_text("utf-8"))
    course = payload["course"]
    steps = course["steps"]
    assert [s["no"] for s in steps] == list(range(1, len(steps) + 1)) and len(steps) <= 5
    assert all(s["instruction"].strip() for s in steps)
    assert course["media_path"] is None or course["media_path"].startswith("/media/")
    with Session.begin() as db:
        if not db.get(Skill, payload["skill"]["id"]):
            db.add(Skill(id=payload["skill"]["id"], name=payload["skill"]["name"]))
            db.flush()
        old = db.scalar(select(Course).where(Course.id == course["id"]))
        if old and old.data != course:
            raise RuntimeError("Course changed: increment revision with a migration; no silent overwrite")
        if not old:
            db.add(Course(id=course["id"], skill_id=payload["skill"]["id"], data=course))


def seed():
    for path in sorted((ROOT / "data/courses").glob("*.json")):
        seed_one(path)


if __name__ == "__main__":
    seed()
