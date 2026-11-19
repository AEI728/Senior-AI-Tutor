import os
from pathlib import Path
import pytest

# Explicit test database. Never overwrite a non-test production database.
os.environ.setdefault("APP_ENV", "test")
test_db = Path(__file__).resolve().parents[3] / "artifacts/databases/api-test.db"
test_db.parent.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", "sqlite:///" + test_db.as_posix())
os.environ["LLM_PROVIDER"] = "mock"
os.environ["AUDIO_PROVIDER"] = "mock"
os.environ["REQUESTS_PER_MINUTE"] = "10000"
from app.db import Base, engine, Session  # noqa: E402
from app.seed import seed  # noqa: E402
from app.main import app, rates  # noqa: E402
from app.auth import local_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def reset():
    if os.environ.get("APP_ENV") != "test" or "test" not in str(engine.url):
        raise RuntimeError("Refusing to reset non-test database")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    rates.clear()
    yield


@pytest.fixture
def http():
    with TestClient(app) as c:
        c.headers["Authorization"] = "Bearer " + local_token()
        yield c


@pytest.fixture
def db():
    with Session() as s:
        yield s
