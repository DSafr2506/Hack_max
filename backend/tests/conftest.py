import json
import os
import tempfile
from datetime import timedelta
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["MAX_BOT_TOKEN"] = "test-bot-token"
os.environ["MAX_BOT_NAME"] = "test_bot"
os.environ["JWT_SECRET"] = "test-secret-at-least-32-bytes-long-000"
os.environ["PUBLIC_URL"] = "https://example.org"
os.environ["DEV_FAKE_AUTH"] = "0"
os.environ["SEED_IF_EMPTY"] = "0"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import maxapi  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Event, utcnow  # noqa: E402


class FakeMax:
    """Поддельный сервер MAX Bot API поверх httpx.MockTransport: пишет все запросы."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.send_status = 200
        self.updates: list[dict] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/messages" and request.method == "POST":
            if self.send_status != 200:
                return httpx.Response(self.send_status, json={"code": "error", "message": "fail"})
            return httpx.Response(200, json={"message": {"body": {"mid": "mid.1", "seq": 1}}})
        if path == "/answers":
            return httpx.Response(200, json={"success": True})
        if path == "/me":
            return httpx.Response(200, json={"user_id": 999, "username": "test_bot", "is_bot": True})
        if path == "/subscriptions" and request.method == "GET":
            return httpx.Response(200, json={"subscriptions": [{"url": "https://old.example/hook"}]})
        if path == "/subscriptions" and request.method in ("DELETE", "POST"):
            return httpx.Response(200, json={"success": True})
        if path == "/updates":
            batch, self.updates = self.updates, []
            return httpx.Response(200, json={"updates": batch, "marker": 42})
        return httpx.Response(404, json={"code": "not.found"})

    def sent(self, path: str = "/messages") -> list[dict]:
        return [json.loads(r.content) for r in self.requests if r.url.path == path and r.method == "POST"]


@pytest.fixture
def fake_max():
    fake = FakeMax()
    client = maxapi.MaxClient(transport=httpx.MockTransport(fake.handler), sleep=lambda s: None)
    maxapi.set_client(client)
    yield fake
    maxapi.set_client(None)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def api():
    from app.main import create_app

    with TestClient(create_app(start_background=False)) as c:
        yield c


def make_init_data(user_id: int = 12345, start_param: str | None = None, age: timedelta = timedelta(0)) -> str:
    from urllib.parse import quote

    params = {
        "auth_date": str(int((utcnow() - age).timestamp())),
        "query_id": "q-1",
        "user": json.dumps({"id": user_id, "first_name": "Имя", "last_name": "Фамилия", "username": "u"}),
        "chat": json.dumps({"id": 1, "type": "DIALOG"}),
    }
    if start_param:
        params["start_param"] = start_param
    h = maxapi.sign_init_data(params, os.environ["MAX_BOT_TOKEN"])
    return "&".join(f"{k}={quote(v)}" for k, v in params.items()) + f"&hash={h}"


def add_event(db, **kw) -> Event:
    now = utcnow()
    data = dict(
        slug="olymp-1",
        type="olympiad",
        title="Олимпиада по математике",
        source_url="https://org.example/olymp",
        registration_url="https://org.example/register",
        registration_deadline=now + timedelta(days=10),
        starts_at=now + timedelta(days=20),
        status="published",
        verified_at=now,
        goal_codes=",admission,",
    )
    data.update(kw)
    e = Event(**data)
    db.add(e)
    db.commit()
    return e


FIXTURES = Path(__file__).parent / "fixtures"
