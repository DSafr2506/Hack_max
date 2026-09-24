"""Сквозная проверка с настоящим ботом, без фронта.

Сначала запустить бэкенд: uvicorn app.main:app --reload
Потом:                    python -m scripts.demo_flow <ваш user_id в MAX>

Скрипт заводит демо-мероприятие, входит от вашего имени (подписывает initData токеном бота,
как это делает MAX), жмёт «Участвую» и запускает демо-напоминание. Через ≤30 секунд
оно придёт в MAX.
"""

import json
import sys
import time
from datetime import timedelta
from urllib.parse import quote

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, init_db
from app.maxapi import sign_init_data
from app.models import Event, utcnow

BASE = "http://127.0.0.1:8000"


def ensure_demo_event() -> Event:
    init_db()
    db = SessionLocal()
    try:
        event = db.scalar(select(Event).where(Event.slug == "demo-olympiad"))
        now = utcnow()
        if event is None:
            event = Event(slug="demo-olympiad", type="olympiad", source_url="https://olimpiada.ru/")
            db.add(event)
        event.title = "Демо: олимпиада по математике"
        event.short_description = "Тестовое мероприятие для проверки напоминаний"
        event.organizer = "Демо-организатор"
        event.format = "online"
        event.registration_url = "https://olimpiada.ru/"
        event.registration_deadline = now + timedelta(days=10)
        event.starts_at = now + timedelta(days=20)
        event.goal_codes = ",admission,"
        event.source_name = "olimpiada.ru"
        event.verified_at = now
        event.status = "published"
        db.commit()
        return event
    finally:
        db.close()


def signed_init_data(user_id: str) -> str:
    params = {"auth_date": str(int(time.time())), "query_id": "demo", "user": json.dumps({"id": int(user_id)})}
    h = sign_init_data(params, settings.max_bot_token)
    return "&".join(f"{k}={quote(v)}" for k, v in params.items()) + f"&hash={h}"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.demo_flow <user_id>")
    user_id = sys.argv[1]
    event = ensure_demo_event()
    print(f"событие #{event.id}: {event.title}")

    # trust_env=False: локальный сервер, системный прокси Windows сюда вмешиваться не должен
    with httpx.Client(base_url=BASE, timeout=10, trust_env=False) as c:
        r = c.post("/api/auth/launch", json={"init_data": signed_init_data(user_id)})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        print("вход:", "новый пользователь" if r.json()["is_new"] else "существующий пользователь")

        r = c.post("/api/me/participations", json={"event_id": event.id, "status": "going"}, headers=h)
        r.raise_for_status()
        print("участие:", r.json()["status"])

        cal = c.get("/api/me/calendar", headers=h).json()
        for item in cal:
            print(f"календарь: {item['kind']:8} {item['at']}  {item['title']}")

        r = c.post("/api/demo/fire-reminder", json={"event_id": event.id, "delay_seconds": 0}, headers=h)
        r.raise_for_status()
        print("демо-напоминание поставлено, придёт в MAX в течение 30 секунд")


if __name__ == "__main__":
    main()
