"""Add three owned example videos once on explicit request; never seed at startup."""
import hashlib
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.config import settings  # noqa: E402
from app.db import Session, User, Work, WorkVideo  # noqa: E402
from app.examples import example_items, example_video  # noqa: E402

if settings().app_env != "local":
    raise SystemExit("Local environment required")
with Session.begin() as db:
    user = db.scalar(select(User).where(User.auth_subject == "xiaoban-local:demo-user"))
    if not user:
        raise SystemExit("Open the local app once before adding examples")
    prefix = "sample-own-" + hashlib.sha256(user.id.encode()).hexdigest()[:12] + "-"
    existing = db.scalars(select(Work).where(Work.user_id == user.id, Work.id.startswith(prefix))).all()
    if existing:
        print("Existing sample uploads retained:", len(existing))
    else:
        courses = {"home-gardening": "repotting-basics", "calligraphy": "calligraphy-lines", "photography": "phone-composition", "music": "rhythm-basics"}
        for i, example in enumerate(random.SystemRandom().sample(example_items(), 3)):
            wid = prefix + str(i)
            db.add(Work(id=wid, user_id=user.id, course_id=courses[example["skill_id"]], title=example["title"] + "（示例）", description="示例视频", state="PENDING", created_at=(datetime.now(timezone.utc) - timedelta(days=i + 1)).isoformat()))
            db.flush()
            db.add(WorkVideo(work_id=wid, video_data=example_video(example["id"]).read_bytes(), media_type="video/mp4"))
        print("Added 3 playable sample uploads to local My works")
