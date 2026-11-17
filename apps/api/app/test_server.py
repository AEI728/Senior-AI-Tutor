"""Disposable local E2E server; forbidden outside APP_ENV=test."""

import os
from alembic.config import Config
from alembic import command
import uvicorn

if os.environ.get("APP_ENV") != "test" or "test" not in os.environ.get("DATABASE_URL", ""):
    raise SystemExit("Dedicated test database required")
command.upgrade(Config("alembic.ini"), "head")
from .seed import seed  # noqa: E402

seed()
uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
