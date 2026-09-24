from app import seed
from tests.conftest import add_event, make_init_data


def test_dicts(api):
    d = api.get("/api/dicts").json()
    assert {g["code"] for g in d["goal"]} == {"admission", "money", "free_trip", "career", "portfolio", "skills", "team"}
    assert any(c["name"] == "Абакан" and c["region_code"] == "19" for c in d["city"])


def test_feed_has_no_description_card_has_trust(api, db):
    add_event(db, description="длинное описание")
    feed = api.get("/api/events?goals=admission&sort=deadline").json()
    assert feed["total"] == 1 and "description" not in feed["items"][0]
    card = api.get("/api/events/olymp-1").json()
    assert card["description"] == "длинное описание"
    assert card["trust"]["source_url"] and card["trust"]["verified_at"]
    assert card["action"]["go_url"] == f"/go/{card['id']}"


def test_my_status_in_feed(api, db, fake_max):
    e = add_event(db)
    token = api.post("/api/auth/launch", json={"init_data": make_init_data(5)}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    api.post("/api/me/participations", json={"event_id": e.id}, headers=h)
    assert api.get("/api/events", headers=h).json()["items"][0]["my_status"] == "going"
    assert api.get("/api/events").json()["items"][0]["my_status"] is None


def test_onboarding_city_sets_region(api):
    token = api.post("/api/auth/launch", json={"init_data": make_init_data(6)}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = api.post(
        "/api/me/onboarding",
        json={"grade": 10, "city": "Абакан", "type_codes": ["olympiad", "hackathon"], "goal_codes": ["admission"]},
        headers=h,
    )
    assert r.status_code == 200, r.text
    me = r.json()
    assert me["region_code"] == "19" and me["onboarded"] and me["type_codes"] == ["olympiad", "hackathon"]
    assert api.patch("/api/me", json={"goal_codes": ["nonsense"]}, headers=h).status_code == 422


def test_ics(api, db):
    add_event(db)
    r = api.get("/api/events/olymp-1.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert "UID:event-1@" in body and "UID:event-1-deadline@" in body and "BEGIN:VALARM" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    links = api.get("/api/events/olymp-1/calendar-links").json()
    assert links["google"].startswith("https://calendar.google.com/calendar/render?action=TEMPLATE")


def test_similar(api, db):
    add_event(db)
    add_event(db, slug="olymp-2")
    assert [e["slug"] for e in api.get("/api/events/olymp-1/similar").json()] == ["olymp-2"]


def test_seed_file_is_valid(db):
    items = seed.load_events()
    created, updated = seed.seed(db, items)
    assert created == len(items) and updated == 0
    assert seed.seed(db, items) == (0, len(items))  # повторный запуск не плодит дубли


def test_admin_requires_token(api, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_token", "adm")
    assert api.get("/api/admin/stats").status_code == 401
    assert api.get("/api/admin/stats", headers={"X-Admin-Token": "adm"}).status_code == 200


def test_feed_full_detail(api, db):
    add_event(db, description="полное")
    item = api.get("/api/events?detail=full&limit=200").json()["items"][0]
    assert item["description"] == "полное" and item["trust"]["source_url"] and item["action"]["go_url"]


def test_seed_if_empty(db):
    from app.main import seed_if_empty
    from app.models import Event

    seed_if_empty()
    n = db.query(Event).count()
    assert n > 30
    seed_if_empty()  # повторно не грузит
    assert db.query(Event).count() == n
