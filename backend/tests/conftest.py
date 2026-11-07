import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
TEST_DB = BACKEND / "test_udyam.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["LLM_PROVIDER"] = "template"
os.environ["OTP_MODE"] = "mock"
os.environ["SLA_JOB_ENABLED"] = "false"
os.environ["NOTIFY_DISPATCH_ENABLED"] = "false"
os.environ["RETENTION_JOB_ENABLED"] = "false"
os.environ["LOOKUP_RATE_LIMIT"] = "1000"
os.environ["OTP_IP_RATE_LIMIT"] = "100000"
os.environ["NOTIFY_PROVIDER"] = "mock"
os.environ["VOICE_PROVIDER"] = "browser"
TEST_STORAGE = BACKEND / "test_storage"
os.environ["UPLOAD_DIR"] = str(TEST_STORAGE)

from app.rules.catalogue import from_csv  # noqa: E402

DATA = BACKEND.parent / "data"


@pytest.fixture(scope="session")
def catalogue():
    return from_csv(DATA / "product_catalogue.csv")


@pytest.fixture(scope="session")
def seeded():
    if TEST_DB.exists():
        TEST_DB.unlink()
    from app import seed

    seed.run(DATA, score=False, verbose=False)
    yield
    TEST_DB.unlink(missing_ok=True)
    import shutil

    shutil.rmtree(TEST_STORAGE, ignore_errors=True)


@pytest.fixture()
def client(seeded):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/api/v1/auth/otp/request", json={"phone": "+919812345678"})
    code = r.json()["dev_code"]
    r = client.post("/api/v1/auth/otp/verify", json={"request_id": r.json()["request_id"], "code": code, "language": "en"})
    return {"Authorization": f"Bearer {r.json()['token']}"}
