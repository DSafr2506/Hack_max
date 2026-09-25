"""Модерация и цифры для демо. Защита — заголовок X-Admin-Token."""

import hmac
import logging
import re
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import extract, fetch, seed
from app.catalog import event_full
from app.config import settings
from app.db import get_db
from app.models import Candidate, Click, Event, Participation, Reminder, ShareLink, User, utcnow

log = logging.getLogger("app.admin")


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.admin_token or not hmac.compare_digest(x_admin_token or "", settings.admin_token):
        raise HTTPException(401, detail={"code": "unauthorized", "message": "admin token required"})


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])
page_router = APIRouter()


@page_router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
def admin_page() -> str:
    """Экран модерации: слева текст страницы, справа поля кандидата. Токен вводится на странице."""
    return (Path(__file__).parent / "admin_page.html").read_text(encoding="utf-8")


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


# ─────────────────────────── кандидаты (H8.4) ───────────────────────────


def _candidate_out(c: Candidate, with_text: bool = False) -> dict[str, Any]:
    out = {
        "id": c.id,
        "status": c.status,
        "confidence": c.confidence,
        "payload": c.payload or {},
        "event_id": c.event_id,
        "model_name": c.model_name,
        "prompt_version": c.prompt_version,
        "reject_reason": c.reject_reason,
        "edited_fields": c.edited_fields or [],
        "cost_usd": c.cost_usd,
        "source_url": c.raw_document.url if c.raw_document else (c.payload or {}).get("source_url"),
    }
    if with_text:
        out["text"] = c.raw_document.text if c.raw_document else ""
    return out


def _cand(db: Session, cid: int) -> Candidate:
    c = db.get(Candidate, cid)
    if c is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "candidate_not_found"})
    return c


@router.get("/candidates")
def list_candidates(status: str | None = "new", db: Session = Depends(get_db)) -> list[dict]:
    q = select(Candidate)
    if status:
        q = q.where(Candidate.status == status)
    return [_candidate_out(c) for c in db.scalars(q.order_by(Candidate.confidence.desc(), Candidate.id))]


@router.get("/candidates/{cid}")
def get_candidate(cid: int, db: Session = Depends(get_db)) -> dict:
    return _candidate_out(_cand(db, cid), with_text=True)


class CandidatePatch(BaseModel):
    payload: dict[str, Any]


@router.patch("/candidates/{cid}")
def patch_candidate(cid: int, body: CandidatePatch, db: Session = Depends(get_db)) -> dict:
    c = _cand(db, cid)
    merged = {**(c.payload or {}), **body.payload}
    original = c.original_payload or {}
    c.edited_fields = sorted(k for k in merged if k != "checks" and merged.get(k) != original.get(k))
    c.payload = merged
    db.commit()
    return _candidate_out(c)


def _slug(title: str, cid: int) -> str:
    table = str.maketrans(
        "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
        "abvgdeejzijklmnoprstufhccss_y_eua",
    )
    base = re.sub(r"[^a-z0-9]+", "-", title.lower().translate(table)).strip("-")[:60]
    return f"{base or 'event'}-c{cid}"


@router.post("/candidates/{cid}/approve")
def approve_candidate(cid: int, db: Session = Depends(get_db)) -> dict:
    """Одобрение человеком — единственный путь кандидата в ленту. verified_at = сейчас."""
    c = _cand(db, cid)
    if c.status not in ("new", "duplicate"):
        raise HTTPException(409, detail={"code": "conflict", "message": f"status {c.status}"})
    try:
        payload = extract.CandidatePayload.model_validate(c.payload or {})
    except ValidationError as exc:
        raise HTTPException(422, detail={"code": "validation_error", "message": str(exc)[:500]}) from None
    problems = extract.check_codes(payload)
    if problems:
        raise HTTPException(422, detail={"code": "validation_error", "message": "; ".join(problems)})
    item = extract.payload_to_event_item({**payload.model_dump(), "source_url": (c.payload or {}).get("source_url")}, _slug(payload.title, c.id))
    if not item.get("goals"):
        raise HTTPException(422, detail={"code": "validation_error", "message": "укажите хотя бы одну цель (goals)"})
    try:
        event, _ = seed.upsert_event(db, item)
    except seed.SeedError as exc:
        raise HTTPException(422, detail={"code": "validation_error", "message": str(exc)}) from None
    event.verified_at = utcnow()
    c.status, c.event_id, c.reviewed_at = "approved", event.id, utcnow()
    db.commit()
    return {"candidate": _candidate_out(c), "event": event_full(event)}


class RejectIn(BaseModel):
    reason: str = ""


@router.post("/candidates/{cid}/reject")
def reject_candidate(cid: int, body: RejectIn, db: Session = Depends(get_db)) -> dict:
    c = _cand(db, cid)
    c.status, c.reject_reason, c.reviewed_at = "rejected", body.reason or "отклонено модератором", utcnow()
    db.commit()
    return _candidate_out(c)


_pipeline_lock = threading.Lock()


def _run_pipeline(limit: int) -> None:
    if not _pipeline_lock.acquire(blocking=False):
        return
    try:
        fetch.run(limit)
        extract.run(limit)
    except Exception:
        log.exception("конвейер упал")
    finally:
        _pipeline_lock.release()


@router.post("/pipeline/run")
def run_pipeline(limit: int = 5) -> dict:
    """Собрать страницы источников и извлечь кандидатов в фоне (для демо модерации)."""
    if _pipeline_lock.locked():
        return {"started": False, "message": "уже выполняется"}
    threading.Thread(target=_run_pipeline, args=(min(limit, 30),), daemon=True).start()
    return {"started": True}


@router.get("/quality")
def quality(db: Session = Depends(get_db)) -> dict:
    """H8.5: сколько полей модератор правил в одобренных карточках — честная метрика качества извлечения."""
    approved = list(db.scalars(select(Candidate).where(Candidate.status == "approved")))
    edits = [len(c.edited_fields or []) for c in approved]
    fields: dict[str, int] = {}
    for c in approved:
        for f in c.edited_fields or []:
            fields[f] = fields.get(f, 0) + 1
    all_c = list(db.scalars(select(Candidate)))
    return {
        "approved": len(approved),
        "avg_edited_fields": round(sum(edits) / len(edits), 2) if edits else None,
        "most_edited": sorted(fields.items(), key=lambda kv: -kv[1])[:5],
        "by_status": {s: sum(1 for c in all_c if c.status == s) for s in {c.status for c in all_c}},
        "llm_cost_usd": round(sum(c.cost_usd or 0 for c in all_c), 4),
        "model": settings.llm_model,
    }
