"""Загрузка data/events.yaml в базу: upsert по slug. Запуск: python -m app.seed"""

import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import DATA_DIR, codes, to_csv
from app.db import SessionLocal, init_db
from app.models import Event, utcnow

log = logging.getLogger("app.seed")
MSK = timezone(timedelta(hours=3))

SCALAR_FIELDS = [
    "type", "title", "short_description", "description", "organizer", "organizer_kind",
    "format", "is_federal", "venue_city", "grade_min", "grade_max", "participation",
    "price_kind", "travel_covered", "accommodation_covered", "entry_kind", "selection_note",
    "registration_url", "registration_channel", "level", "source_url", "source_name",
]  # fmt: skip


class SeedError(ValueError):
    pass


def to_dt(value: Any, end_of_day: bool) -> datetime | None:
    """Дата без времени: дедлайн — конец дня по МСК, начало — 10:00 МСК."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time(23, 59) if end_of_day else time(10, 0))
    else:
        text = str(value)
        dt = datetime.fromisoformat(text) if "T" in text or " " in text else None
        if dt is None:
            return to_dt(date.fromisoformat(text), end_of_day)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(timezone.utc)


def validate(item: dict[str, Any]) -> None:
    slug = item.get("slug") or "?"
    if item.get("type") not in codes("type"):
        raise SeedError(f"{slug}: неизвестный type {item.get('type')}")
    if not item.get("title") or not item.get("source_url"):
        raise SeedError(f"{slug}: нет title или source_url")
    bad_goals = set(item.get("goals") or []) - codes("goal")
    if bad_goals or not item.get("goals"):
        raise SeedError(f"{slug}: goals пусты или неизвестны: {bad_goals}")
    bad_subjects = set(item.get("subjects") or []) - codes("subject")
    if bad_subjects:
        raise SeedError(f"{slug}: неизвестные subjects {bad_subjects}")
    if not item.get("registration_deadline") and not item.get("starts_at"):
        raise SeedError(f"{slug}: нужен registration_deadline или starts_at")
    if len(item.get("short_description") or "") > 200:
        raise SeedError(f"{slug}: short_description длиннее 200 символов")


def upsert_event(db: Session, item: dict[str, Any]) -> tuple[Event, bool]:
    validate(item)
    event = db.scalar(select(Event).where(Event.slug == item["slug"]))
    created = event is None
    if created:
        event = Event(slug=item["slug"])
        db.add(event)
    for field in SCALAR_FIELDS:
        if field in item:
            setattr(event, field, item[field])
    event.short_description = item.get("short_description") or ""
    event.description = item.get("description") or ""
    event.region_codes = to_csv([str(r) for r in item.get("region_codes") or []])
    event.goal_codes = to_csv(item.get("goals"))
    event.subject_codes = to_csv(item.get("subjects"))
    event.attributes = item.get("attributes") or {}
    event.registration_deadline = to_dt(item.get("registration_deadline"), end_of_day=True)
    event.starts_at = to_dt(item.get("starts_at"), end_of_day=False)
    event.ends_at = to_dt(item.get("ends_at"), end_of_day=True)
    event.verified_at = to_dt(item.get("verified_at"), end_of_day=False) or utcnow()
    event.freshness = "fresh"
    event.status = item.get("status", "published")
    return event, created


def load_events(path=None) -> list[dict[str, Any]]:
    path = path or DATA_DIR / "events.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def seed(db: Session, items: list[dict[str, Any]]) -> tuple[int, int]:
    created = updated = 0
    for item in items:
        _, is_new = upsert_event(db, item)
        created += is_new
        updated += not is_new
    db.commit()
    return created, updated


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    db = SessionLocal()
    try:
        items = load_events()
        slugs = [i.get("slug") for i in items]
        dupes = {s for s in slugs if slugs.count(s) > 1}
        if dupes:
            sys.exit(f"повторяющиеся slug: {dupes}")
        created, updated = seed(db, items)
        log.info("события: создано %s, обновлено %s, всего в файле %s", created, updated, len(items))
    except SeedError as exc:
        sys.exit(f"ошибка в events.yaml: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
