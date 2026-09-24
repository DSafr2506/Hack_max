"""Модерация и цифры для демо. Защита — заголовок X-Admin-Token."""

import hmac
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.catalog import event_full
from app.config import settings
from app.db import get_db
from app.models import Click, Event, Participation, Reminder, ShareLink, User, utcnow


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token or not hmac.compare_digest(x_admin_token or "", settings.admin_token):
        raise HTTPException(401, detail={"code": "unauthorized", "message": "admin token required"})


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@router.get("/events")
def events_to_review(
    stale_days: int | None = None, freshness: str | None = None, db: Session = Depends(get_db)
) -> list[dict]:
    """Очередь на перепроверку: давно не проверенные и те, где школьники нажали «информация устарела»."""
    q = select(Event).where(Event.status == "published")
    if stale_days is not None:
        q = q.where(Event.verified_at < utcnow() - timedelta(days=stale_days))
    if freshness:
        q = q.where(Event.freshness == freshness)
    return [event_full(e) for e in db.scalars(q.order_by(Event.verified_at))]


def _get(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "event_not_found"})
    return event


@router.post("/events/{event_id}/verify")
def verify(event_id: int, db: Session = Depends(get_db)) -> dict:
    event = _get(db, event_id)
    event.verified_at, event.freshness = utcnow(), "fresh"
    db.commit()
    return event_full(event)


@router.post("/events/{event_id}/archive")
def archive(event_id: int, db: Session = Depends(get_db)) -> dict:
    event = _get(db, event_id)
    event.status = "archived"
    db.commit()
    return {"id": event.id, "status": event.status}


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    """Цифры для питча (раздел 8 записки)."""

    def count(q) -> int:
        return db.scalar(q) or 0

    users = count(select(func.count(User.id)))
    going_users = count(select(func.count(func.distinct(Participation.user_id))).where(Participation.status == "going"))
    return {
        "events_published": count(select(func.count(Event.id)).where(Event.status == "published")),
        "users": users,
        "users_with_going": going_users,
        "clicks_to_source": count(select(func.count(Click.id))),
        "clicks_by_source": dict(db.execute(select(Click.source, func.count(Click.id)).group_by(Click.source)).all()),
        "reminders_sent": count(select(func.count(Reminder.id)).where(Reminder.status == "sent")),
        "followup_answers": count(
            select(func.count(Participation.id)).where(Participation.status.in_(("participated", "skipped")))
        ),
        "share_signups": count(select(func.coalesce(func.sum(ShareLink.signups), 0))),
        "reported_stale": count(select(func.count(Event.id)).where(Event.freshness == "reported")),
    }
