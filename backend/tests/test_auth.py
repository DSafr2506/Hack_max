from datetime import timedelta
from urllib.parse import quote

import pytest

from app import maxapi
from app.config import settings
from tests.conftest import make_init_data

TOKEN = "test-bot-token"


def test_valid_signature():
    data = maxapi.verify_init_data(make_init_data(777, start_param="ev_abc"), TOKEN)
    assert data["external_id"] == "777"
    assert data["start_param"] == "ev_abc"
    assert set(data) == {"external_id", "start_param", "query_id", "auth_date"}  # имени и фото нет


def test_full_launch_url_and_fragment():
    init = make_init_data(778)
    url = "https://app.example/#WebAppData=" + quote(init, safe="") + "&WebAppPlatform=web&WebAppVersion=26.2.8"
    assert maxapi.verify_init_data(url, TOKEN)["external_id"] == "778"


def test_tampered_signature():
    init = make_init_data(777).replace("777", "778")
    with pytest.raises(maxapi.AuthError) as e:
        maxapi.verify_init_data(init, TOKEN)
    assert e.value.code == "max_init_data_signature_mismatch"


def test_wrong_bot_token():
    with pytest.raises(maxapi.AuthError):
        maxapi.verify_init_data(make_init_data(), "other-token")


def test_expired():
    with pytest.raises(maxapi.AuthError) as e:
        maxapi.verify_init_data(make_init_data(age=timedelta(hours=2)), TOKEN)
    assert e.value.code == "max_init_data_expired"


def test_two_hashes():
    init = make_init_data()
    with pytest.raises(maxapi.AuthError) as e:
        maxapi.verify_init_data(init + "&hash=deadbeef", TOKEN)
    assert e.value.code == "max_init_data_hash_invalid"


def test_no_hash():
    init = make_init_data().rsplit("&hash=", 1)[0]
    with pytest.raises(maxapi.AuthError):
        maxapi.verify_init_data(init, TOKEN)


def test_launch_endpoint_issues_token_and_stores_only_id(api, db):
    r = api.post("/api/auth/launch", json={"init_data": make_init_data(4242)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["is_new"] is True
    me = api.get("/api/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    from app.models import User

    user = db.query(User).one()
    assert user.external_id == "4242"
    assert "Имя" not in str(vars(user))


def test_launch_rejects_bad_signature(api):
    r = api.post("/api/auth/launch", json={"init_data": make_init_data().replace("hash=", "hash=00")})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_dev_fake_auth_disabled_by_default(api):
    assert settings.dev_fake_auth is False
    r = api.post("/api/auth/launch", json={"dev_user_id": "1"})
    assert r.status_code == 401


def test_dev_fake_auth_when_enabled(api, monkeypatch):
    monkeypatch.setattr(settings, "dev_fake_auth", True)
    r = api.post("/api/auth/launch", json={"dev_user_id": "1"})
    assert r.status_code == 200


def test_concurrent_first_launch_does_not_fail(db):
    from app import logic
    from app.db import SessionLocal

    other = SessionLocal()
    u1, new1 = logic.get_or_create_user(other, "race")
    # вторая сессия ещё не видит незакоммиченную запись и пытается вставить свою
    other.commit()
    u2, new2 = logic.get_or_create_user(db, "race")
    assert new1 and not new2 and u1.id == u2.id
    other.close()
