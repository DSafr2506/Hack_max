"""Сквозной сценарий: launch → «Участвую» → календарь → напоминание в MAX → клик /go → followup."""

import json
from datetime import timedelta

from app import logic
from app.models import Click, Participation, Reminder, ShareLink
from tests.conftest import FIXTURES, add_event, make_init_data


def test_full_flow(api, db, fake_max, monkeypatch):
    monkeypatch.setattr(logic, "in_quiet_hours", lambda now: False)
    event = add_event(db)

    r = api.post("/api/auth/launch", json={"init_data": make_init_data(12345)})
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    r = api.post("/api/me/participations", json={"event_id": event.id, "status": "going"}, headers=h)
    assert r.status_code == 200, r.text
    r2 = api.post("/api/me/participations", json={"event_id": event.id, "status": "going"}, headers=h)
    assert r2.json()["id"] == r.json()["id"]  # идемпотентно
    assert db.query(Participation).count() == 1

    cal = api.get("/api/me/calendar", headers=h).json()
    assert {c["kind"] for c in cal} == {"deadline", "start"}
    kinds = {r.kind for r in db.query(Reminder).all()}
    assert kinds == {"deadline_3d", "deadline_1d", "start_1d", "followup"}

    # демо-кнопка на сцене
    r = api.post("/api/demo/fire-reminder", json={"event_id": event.id, "delay_seconds": 0}, headers=h)
    assert r.status_code == 200
    assert logic.dispatch_reminders(db) == 1
    msg = fake_max.sent()[-1]
    buttons = [b for row in msg["attachments"][0]["payload"]["buttons"] for b in row]
    link = next(b for b in buttons if b["type"] == "link")
    assert link["url"] == f"https://example.org/go/{event.id}?src=reminder"
    assert any(b["type"] == "open_app" for b in buttons)

    # переход по кнопке: анонимно, как из браузера
    r = api.get(f"/go/{event.id}?src=reminder", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == event.registration_url
    assert db.query(Click).one().source == "reminder"

    # followup: сдвигаем его на «сейчас», отправляем, жмём кнопку
    fu = db.query(Reminder).filter_by(kind="followup").one()
    fu.scheduled_at = logic.utcnow() - timedelta(seconds=1)
    db.commit()
    assert logic.dispatch_reminders(db) == 1
    fu_msg = fake_max.sent()[-1]
    payload = fu_msg["attachments"][0]["payload"]["buttons"][0][0]["payload"]
    assert payload == f"fu:{event.id}:participated"

    cb = json.loads((FIXTURES / "message_callback.json").read_text(encoding="utf-8"))
    cb["callback"]["payload"] = payload
    logic.handle_update(cb)
    db.expire_all()
    assert db.query(Participation).one().status == "participated"
    answer = fake_max.sent("/answers")[-1]
    assert answer["message"]["attachments"] == []  # кнопки сняты


def test_blocked_user_disables_notifications(api, db, fake_max):
    event = add_event(db)
    token = api.post("/api/auth/launch", json={"init_data": make_init_data(1)}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    api.post("/api/demo/fire-reminder", json={"event_id": event.id, "delay_seconds": 0}, headers=h)
    fake_max.send_status = 403
    logic.dispatch_reminders(db)
    assert api.get("/api/me", headers=h).json()["notifications_enabled"] is False


def test_share_attribution_only_new_users(api, db, fake_max):
    event = add_event(db)
    owner = api.post("/api/auth/launch", json={"init_data": make_init_data(1)}).json()["token"]
    share = api.get(f"/api/events/{event.slug}/share", headers={"Authorization": f"Bearer {owner}"}).json()
    token = share["token"]
    assert token.startswith("ev_") and len(token) == 25
    assert all(c.isalnum() or c in "_-" for c in token)
    assert share["deep_link"] == f"https://max.ru/test_bot?startapp={token}"
    assert share["share_url"].startswith("https://max.ru/:share?text=")

    api.post("/api/auth/launch", json={"init_data": make_init_data(2, start_param=token)})
    api.post("/api/auth/launch", json={"init_data": make_init_data(2, start_param=token)})
    api.post("/api/auth/launch", json={"init_data": make_init_data(1, start_param=token)})
    db.expire_all()
    assert db.query(ShareLink).one().signups == 1


def test_go_without_link(api, db):
    event = add_event(db, registration_url=None, registration_channel="school")
    r = api.get(f"/go/{event.id}", follow_redirects=False)
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_external_link"


def test_foreign_participation_forbidden(api, db, fake_max):
    event = add_event(db)
    t1 = api.post("/api/auth/launch", json={"init_data": make_init_data(1)}).json()["token"]
    t2 = api.post("/api/auth/launch", json={"init_data": make_init_data(2)}).json()["token"]
    pid = api.post(
        "/api/me/participations", json={"event_id": event.id}, headers={"Authorization": f"Bearer {t1}"}
    ).json()["id"]
    r = api.patch(
        f"/api/me/participations/{pid}", json={"status": "skipped"}, headers={"Authorization": f"Bearer {t2}"}
    )
    assert r.status_code == 403
