"""Каталог: справочники, фильтр ленты (H2.1), сериализация карточек (H2.2)."""

from datetime import date, datetime, time, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.orm import Session

from app.models import Event, Participation, utcnow

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


# ─────────────────────────── справочники ───────────────────────────


@lru_cache
def dicts() -> dict[str, Any]:
    data = yaml.safe_load((DATA_DIR / "dicts.yaml").read_text(encoding="utf-8"))
    cities = yaml.safe_load((DATA_DIR / "cities.yaml").read_text(encoding="utf-8"))
    data["city"] = sorted(({"name": n, "region_code": r} for n, r in cities), key=lambda c: c["name"])
    return data


def codes(group: str) -> set[str]:
    return {item["code"] for item in dicts()[group]}


def name_of(group: str, code: str | None, key: str = "name") -> str | None:
    for item in dicts()[group]:
        if item["code"] == code:
            return item.get(key) or item["name"]
    return None


def csv_list(value: str | None) -> list[str]:
    return [x for x in (value or "").split(",") if x]


def to_csv(items: list[str] | None) -> str:
    return "," + ",".join(items) + "," if items else ""


# ─────────────────────────── фильтр ───────────────────────────


class EventFilter(BaseModel):
    types: list[str] = []
    goals: list[str] = []
    subjects: list[str] = []
    grade: int | None = Field(default=None, ge=1, le=11)
    region_code: str | None = None
    available_from_region: bool = False
    format: str | None = None
    price_kinds: list[str] = []
    travel_covered: bool = False
    entry_kinds: list[str] = []
    levels: list[str] = []
    deadline_before: date | None = None
    only_with_deadline: bool = False
    only_past: bool = False
    q: str | None = None
    sort: str = "deadline"
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


def _any_code(column, values: list[str]):
    return or_(*[column.like(f"%,{v},%") for v in values])


def build_query(f: EventFilter, now: datetime | None = None):
    now = now or utcnow()
    conds = [Event.status == "published"]

    if f.only_past:
        conds.append(Event.registration_deadline < now)
    else:
        # прошедший дедлайн регистрации — в ленту не попадает; без дедлайна — пока не закончилось
        conds.append(or_(Event.registration_deadline.is_(None), Event.registration_deadline >= now))
        conds.append(
            or_(
                Event.registration_deadline.is_not(None),
                func.coalesce(Event.ends_at, Event.starts_at) >= now,
                and_(Event.ends_at.is_(None), Event.starts_at.is_(None)),
            )
        )

    if f.types:
        conds.append(Event.type.in_(f.types))
    if f.goals:
        conds.append(_any_code(Event.goal_codes, f.goals))
    if f.subjects:
        conds.append(_any_code(Event.subject_codes, f.subjects))
    if f.grade is not None:
        conds.append(or_(Event.grade_min.is_(None), Event.grade_min <= f.grade))
        conds.append(or_(Event.grade_max.is_(None), Event.grade_max >= f.grade))
    if f.region_code and f.available_from_region:
        conds.append(
            or_(
                Event.format != "offline",
                Event.region_codes.like(f"%,{f.region_code},%"),
                and_(Event.is_federal.is_(True), Event.travel_covered.in_(("yes", "partial"))),
            )
        )
    elif f.available_from_region:
        conds.append(Event.format != "offline")
    if f.format:
        conds.append(Event.format == f.format)
    if f.price_kinds:
        conds.append(Event.price_kind.in_(f.price_kinds))
    if f.travel_covered:
        conds.append(Event.travel_covered.in_(("yes", "partial")))
    if f.entry_kinds:
        conds.append(Event.entry_kind.in_(f.entry_kinds))
    if f.levels:
        conds.append(Event.level.in_(f.levels))
    if f.deadline_before:
        end = datetime.combine(f.deadline_before, time.max, tzinfo=timezone.utc)
        conds.append(Event.registration_deadline <= end)
    if f.only_with_deadline:
        conds.append(Event.registration_deadline.is_not(None))
    if f.q:
        needle = f"%{f.q.strip().lower()}%"
        conds.append(
            or_(
                func.lower(Event.title).like(needle),
                func.lower(Event.short_description).like(needle),
                func.lower(Event.organizer).like(needle),
            )
        )
    return select(Event).where(and_(*conds) if conds else false())


def order(q, sort: str):
    if sort == "new":
        return q.order_by(Event.verified_at.desc(), Event.id.desc())
    if sort == "starts":
        return q.order_by(Event.starts_at.is_(None), Event.starts_at, Event.id)
    # по ближайшему дедлайну; без дедлайна — в конце, по дате начала
    return q.order_by(
        Event.registration_deadline.is_(None), Event.registration_deadline, Event.starts_at, Event.id
    )


def search(db: Session, f: EventFilter) -> tuple[list[Event], int]:
    q = build_query(f)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    items = db.scalars(order(q, f.sort).limit(f.limit).offset(f.offset)).all()
    return list(items), total


def similar(db: Session, event: Event, limit: int = 5) -> list[Event]:
    f = EventFilter(types=[event.type], goals=csv_list(event.goal_codes), limit=limit + 1)
    items, _ = search(db, f)
    return [e for e in items if e.id != event.id][:limit]


# ─────────────────────────── сериализация ───────────────────────────


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def my_statuses(db: Session, user_id: int | None, event_ids: list[int]) -> dict[int, str]:
    if not user_id or not event_ids:
        return {}
    rows = db.execute(
        select(Participation.event_id, Participation.status).where(
            Participation.user_id == user_id, Participation.event_id.in_(event_ids)
        )
    )
    return {eid: status for eid, status in rows}


def event_short(e: Event, my_status: str | None = None) -> dict[str, Any]:
    return {
        "id": e.id,
        "slug": e.slug,
        "type": e.type,
        "type_name": name_of("type", e.type, "short"),
        "title": e.title,
        "short_description": e.short_description,
        "organizer": e.organizer,
        "format": e.format,
        "venue_city": e.venue_city,
        "is_federal": e.is_federal,
        "grade_min": e.grade_min,
        "grade_max": e.grade_max,
        "registration_deadline": _iso(e.registration_deadline),
        "starts_at": _iso(e.starts_at),
        "ends_at": _iso(e.ends_at),
        "price_kind": e.price_kind,
        "travel_covered": e.travel_covered,
        "entry_kind": e.entry_kind,
        "level": e.level,
        "goal_codes": csv_list(e.goal_codes),
        "subject_codes": csv_list(e.subject_codes),
        "freshness": e.freshness,
        "my_status": my_status,
    }


def event_full(e: Event, my_status: str | None = None) -> dict[str, Any]:
    data = event_short(e, my_status)
    data.update(
        {
            "description": e.description,
            "organizer_kind": e.organizer_kind,
            "region_codes": csv_list(e.region_codes),
            "participation": e.participation,
            "accommodation_covered": e.accommodation_covered,
            "selection_note": e.selection_note,
            "attributes": e.attributes or {},
            "trust": {
                "source_url": e.source_url,
                "source_name": e.source_name,
                "verified_at": _iso(e.verified_at),
                "freshness": e.freshness,
            },
            "action": {
                "go_url": f"/go/{e.id}",
                "has_external_registration": bool(e.registration_url),
                "channel": e.registration_channel,
            },
        }
    )
    return data
