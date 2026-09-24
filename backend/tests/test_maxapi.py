"""Клиент Bot API и обработка апдейтов бота на поддельном сервере MAX."""

import json

from app import logic, maxapi
from app.models import Reminder, User
from tests.conftest import FIXTURES, add_event


def test_send_message_request_format(fake_max):
    res = maxapi.get_client().send_message("12345", "Привет", [[maxapi.btn_callback("Ок", "ping")]])
    assert res.ok and res.message_id == "mid.1"
    req = fake_max.requests[-1]
    assert req.url.host == "platform-api2.max.ru"
    assert req.headers["Authorization"] == "test-bot-token"  # без Bearer
    assert req.url.params["user_id"] == "12345"
    body = json.loads(req.content)
    assert body["format"] == "markdown"
    assert body["attachments"][0]["type"] == "inline_keyboard"
    assert body["attachments"][0]["payload"]["buttons"][0][0]["payload"] == "ping"


def test_send_message_retries_without_buttons_on_400(fake_max):
    calls = {"n": 0}
    orig = fake_max.handler

    def handler(request):
        if request.url.path == "/messages":
            calls["n"] += 1
            if "attachments" in json.loads(request.content):
                fake_max.requests.append(request)
                import httpx

                return httpx.Response(400, json={"code": "proto.payload", "message": "bad url"})
        return orig(request)

    fake_max.handler = handler
    import httpx

    client = maxapi.MaxClient(transport=httpx.MockTransport(handler), sleep=lambda s: None)
    assert client.send_message("1", "t", [[maxapi.btn_link("x", "http://localhost/go/1")]]).ok
    assert calls["n"] == 2


def test_open_app_button_uses_bot_name():
    b = maxapi.btn_open_app("Открыть", "e_1")
    assert b == {"type": "open_app", "text": "Открыть", "web_app": "test_bot", "payload": "e_1"}


def test_drop_webhooks(fake_max):
    assert maxapi.get_client().drop_webhooks() == 1
    deletes = [r for r in fake_max.requests if r.method == "DELETE"]
    assert deletes[0].url.params["url"] == "https://old.example/hook"


def test_update_user_id_all_shapes():
    for name in ("message_callback", "bot_started", "bot_stopped", "message_created"):
        u = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert maxapi.update_user_id(u) == "12345", name


def test_scrub_removes_names():
    u = {"user": {"user_id": 1, "first_name": "Иван", "username": "ivan"}}
    assert maxapi.scrub(u) == {"user": {"user_id": 1, "first_name": "***", "username": "***"}}


def test_bot_started_and_stopped(fake_max, db):
    started = json.loads((FIXTURES / "bot_started.json").read_text(encoding="utf-8"))
    logic.handle_update(started)
    user = db.query(User).one()
    assert user.notifications_enabled
    welcome = fake_max.sent()[-1]
    assert welcome["attachments"][0]["payload"]["buttons"][0][0]["type"] == "open_app"

    event = add_event(db)
    logic.set_participation(db, user, event, "going")
    assert db.query(Reminder).filter_by(status="pending").count() > 0

    logic.handle_update(json.loads((FIXTURES / "bot_stopped.json").read_text(encoding="utf-8")))
    db.expire_all()
    assert not db.query(User).one().notifications_enabled
    assert db.query(Reminder).filter_by(status="pending").count() == 0


def test_start_command(fake_max, db):
    logic.handle_update(json.loads((FIXTURES / "message_created.json").read_text(encoding="utf-8")))
    assert db.query(User).one().notifications_enabled
    assert len(fake_max.sent()) == 1


def test_stale_callback_marks_event(fake_max, db):
    event = add_event(db)
    cb = json.loads((FIXTURES / "message_callback.json").read_text(encoding="utf-8"))
    cb["callback"]["payload"] = f"stale:{event.id}"
    logic.handle_update(cb)
    db.expire_all()
    assert event.freshness == "reported"
    answer = fake_max.sent("/answers")[-1]
    assert "notification" in answer


def test_unknown_callback_still_answered(fake_max):
    cb = json.loads((FIXTURES / "message_callback.json").read_text(encoding="utf-8"))
    cb["callback"]["payload"] = "garbage"
    logic.handle_update(cb)
    assert len(fake_max.sent("/answers")) == 1


def test_poller_saves_marker(fake_max):
    fake_max.updates = [json.loads((FIXTURES / "message_created.json").read_text(encoding="utf-8"))]
    seen = []
    poller = maxapi.Poller(maxapi.get_client(), seen.append)
    result = poller.client.get_updates(None, timeout=0)
    updates, marker = result
    for u in updates:
        poller.handler(u)
    logic.save_marker(marker)
    assert seen and logic.load_marker() == 42


def test_quiet_hours():
    from datetime import datetime, timezone

    night = datetime(2026, 9, 23, 20, 0, tzinfo=timezone.utc)  # 23:00 МСК
    day = datetime(2026, 9, 23, 9, 0, tzinfo=timezone.utc)  # 12:00 МСК
    assert logic.in_quiet_hours(night) and not logic.in_quiet_hours(day)
    assert logic.next_morning(night) == datetime(2026, 9, 24, 5, 0, tzinfo=timezone.utc)


def test_webhook_secret_and_dispatch(api, db, fake_max, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_webhook_secret", "s3cret_value")
    update = json.loads((FIXTURES / "bot_started.json").read_text(encoding="utf-8"))
    assert api.post("/max/webhook", json=update).status_code == 401
    r = api.post("/max/webhook", json=update, headers={"X-Max-Bot-Api-Secret": "s3cret_value"})
    assert r.status_code == 200
    assert db.query(User).one().notifications_enabled
    assert len(fake_max.sent()) == 1  # приветствие


def test_ensure_webhook_resubscribes(fake_max, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_mode", "webhook")
    monkeypatch.setattr(settings, "max_webhook_secret", "s3cret_value")
    assert maxapi.ensure_webhook()
    sub = fake_max.sent("/subscriptions")[-1]
    assert sub["url"] == "https://example.org/max/webhook"
    assert sub["secret"] == "s3cret_value"
    assert "message_callback" in sub["update_types"]
