"""Извлечение мероприятия из сохранённой страницы: текст → LLM → проверка → кандидат на модерацию.

Автопубликации нет: кандидат становится событием только после одобрения человеком.
Запуск: python -m app.extract --limit 10
"""

import argparse
import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import llm
from app.catalog import codes, dicts
from app.config import settings
from app.db import SessionLocal, init_db
from app.models import Candidate, Event, RawDocument

log = logging.getLogger("app.extract")

PROMPT_VERSION = "extract_v1"
PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / f"{PROMPT_VERSION}.txt"
MAX_TEXT = 12_000  # символов страницы в промпт: хватает на карточку мероприятия и не раздувает стоимость
REQUIRED = ("title", "type", "source_url", "date", "place")

CODE_FIELDS = {
    "type": {"olympiad", "camp", "hackathon", "career", "grant", "volunteering", "sport", "creative"},
    "organizer_kind": {"gov", "university", "company", "ngo", "other"},
    "format": {"online", "offline", "hybrid"},
    "participation": {"individual", "team", "both"},
    "price_kind": {"free", "paid", "quota", "unknown"},
    "travel_covered": {"yes", "partial", "no", "unknown"},
    "accommodation_covered": {"yes", "partial", "no", "unknown"},
    "entry_kind": {"open", "selection", "by_result", "invite_only"},
    "level": {"school", "municipal", "regional", "federal", "international"},
}


class CandidatePayload(BaseModel):
    """То, что должна вернуть модель. Лишнее отбрасывается, неизвестные коды — ошибка."""

    title: str = Field(min_length=3, max_length=300)
    type: str
    short_description: str = ""
    description: str = ""
    organizer: str = ""
    organizer_kind: str = "other"
    format: str = "online"
    region_codes: list[str] = []
    is_federal: bool = False
    venue_city: str | None = None
    grade_min: int | None = Field(default=None, ge=1, le=11)
    grade_max: int | None = Field(default=None, ge=1, le=11)
    participation: str = "individual"
    registration_deadline: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    price_kind: str = "unknown"
    travel_covered: str = "unknown"
    accommodation_covered: str = "unknown"
    entry_kind: str = "open"
    selection_note: str | None = None
    registration_url: str | None = None
    level: str | None = None
    goals: list[str] = []
    subjects: list[str] = []
    benefit_note: str | None = None

    @field_validator("registration_deadline", "starts_at", "ends_at")
    @classmethod
    def iso_date(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        try:
            (datetime.fromisoformat(v) if "T" in v else date.fromisoformat(v))
        except ValueError:
            raise ValueError(f"дата не в ISO 8601: {v}") from None
        return v

    @field_validator("short_description")
    @classmethod
    def short(cls, v: str) -> str:
        return (v or "")[:200]


def check_codes(p: CandidatePayload) -> list[str]:
    errors = []
    for field, allowed in CODE_FIELDS.items():
        value = getattr(p, field)
        if value is not None and value not in allowed:
            errors.append(f"{field}: недопустимое значение {value!r}")
    for field, group in (("goals", "goal"), ("subjects", "subject"), ("region_codes", "region")):
        bad = set(getattr(p, field)) - codes(group)
        if bad:
            errors.append(f"{field}: неизвестные коды {sorted(bad)}")
    return errors


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()


def enforce_no_invention(p: CandidatePayload, text: str) -> list[str]:
    """Правило 1: бесплатность, проезд и льготы — только если об этом прямо написано на странице."""
    t = _norm(text)
    notes = []
    if p.price_kind == "free" and not re.search(r"бесплатн|без оплаты|за счет|за счёт", t):
        p.price_kind = "unknown"
        notes.append("price_kind сброшен: в тексте нет слов о бесплатности")
    if p.travel_covered in ("yes", "partial") and not re.search(r"проезд|дорог[аиу]|трансфер|билет", t):
        p.travel_covered = "unknown"
        notes.append("travel_covered сброшен: в тексте нет слов о проезде")
    if p.accommodation_covered in ("yes", "partial") and not re.search(r"прожива|размещ|питани", t):
        p.accommodation_covered = "unknown"
        notes.append("accommodation_covered сброшен: в тексте нет слов о проживании")
    if p.benefit_note:
        quote = _norm(p.benefit_note)[:60]
        if quote and quote not in t:
            p.benefit_note = None
            notes.append("benefit_note удалён: не является цитатой со страницы")
    if "admission" in p.goals and not re.search(r"поступлен|бви|без вступительн|баллов|вуз", t):
        p.goals = [g for g in p.goals if g != "admission"]
        notes.append("goal admission удалён: на странице нет слов о поступлении")
    return notes


def confidence(p: CandidatePayload, source_url: str) -> float:
    have = {
        "title": bool(p.title),
        "type": bool(p.type),
        "source_url": bool(source_url),
        "date": bool(p.registration_deadline or p.starts_at),
        "place": bool(p.format and (p.format == "online" or p.region_codes or p.is_federal or p.venue_city)),
    }
    return round(sum(have.values()) / len(REQUIRED), 2)


def dedup_key(title: str, organizer: str, start: str | None) -> str:
    return f"{_norm(title)}|{_norm(organizer)}|{(start or '')[:10]}"


def find_duplicate(db: Session, p: CandidatePayload) -> int | None:
    key = dedup_key(p.title, p.organizer, p.starts_at)
    for e in db.scalars(select(Event).where(Event.status != "archived")):
        start = e.starts_at.date().isoformat() if e.starts_at else None
        if dedup_key(e.title, e.organizer, start) == key or _norm(e.title) == _norm(p.title):
            return e.id
    return None


def build_messages(text: str, url: str) -> list[dict[str, str]]:
    d = dicts()
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = (
        template.replace("{types}", ", ".join(sorted(CODE_FIELDS["type"])))
        .replace("{goals}", ", ".join(f"{g['code']} ({g['name']})" for g in d["goal"]))
        .replace("{subjects}", ", ".join(s["code"] for s in d["subject"]))
        .replace("{regions}", ", ".join(f"{r['code']} {r['name']}" for r in d["region"]))
        .replace("{url}", url)
        .replace("{text}", text[:MAX_TEXT])
    )
    return [
        {"role": "system", "content": "Ты аккуратно извлекаешь факты из текста и отвечаешь только JSON."},
        {"role": "user", "content": prompt},
    ]


def extract_document(db: Session, doc: RawDocument) -> Candidate:
    """Одна страница → один кандидат (new / rejected / duplicate). Невалидный ответ — один переспрос."""
    messages = build_messages(doc.text, doc.url)
    cand = Candidate(raw_document_id=doc.id, model_name=settings.llm_model, prompt_version=PROMPT_VERSION)
    tokens_in = tokens_out = 0
    cost = 0.0
    payload: CandidatePayload | None = None
    error = ""
    for attempt in range(2):
        try:
            result = llm.chat_json(messages)
        except llm.LLMParseError as exc:
            tokens_in, tokens_out, cost = tokens_in + exc.tokens_in, tokens_out + exc.tokens_out, cost + (exc.cost or 0)
            error = f"ответ не JSON: {exc}"
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": exc.raw[:4000]},
                    {"role": "user", "content": f"Ответ не прошёл проверку: {error}\nВерни только JSON-объект по схеме."},
                ]
            continue
        except llm.LLMError as exc:
            error = f"LLM недоступна: {exc}"
            break
        tokens_in += result.tokens_in
        tokens_out += result.tokens_out
        cost += result.cost_usd or 0.0
        cand.model_name = result.model
        if result.data.get("not_an_event"):
            error = "not_an_event"
            break
        try:
            payload = CandidatePayload.model_validate(result.data)
            problems = check_codes(payload)
            if problems:
                raise ValueError("; ".join(problems))
            break
        except (ValidationError, ValueError) as exc:
            payload = None
            error = str(exc)[:800]
            if attempt == 0:
                messages = messages + [
                    {"role": "assistant", "content": result.raw},
                    {"role": "user", "content": f"Ответ не прошёл проверку: {error}\nИсправь и верни JSON заново."},
                ]

    cand.tokens_in, cand.tokens_out, cand.cost_usd = tokens_in, tokens_out, round(cost, 6)
    if payload is None:
        cand.status, cand.reject_reason, cand.payload, cand.confidence = "rejected", error, {}, 0.0
    else:
        notes = enforce_no_invention(payload, doc.text)
        data = payload.model_dump()
        data["source_url"] = doc.url
        data["checks"] = notes
        cand.payload = data
        cand.original_payload = dict(data)
        cand.confidence = confidence(payload, doc.url)
        dup = find_duplicate(db, payload)
        cand.status, cand.event_id = ("duplicate", dup) if dup else ("new", None)
    db.add(cand)
    db.commit()
    return cand


def payload_to_event_item(payload: dict[str, Any], slug: str) -> dict[str, Any]:
    """Кандидат → запись в формате events.yaml для seed.upsert_event."""
    item = {k: v for k, v in payload.items() if k not in ("checks",) and v is not None}
    item["slug"] = slug
    item["registration_channel"] = "external" if payload.get("registration_url") else "school"
    item.setdefault("source_name", re.sub(r"^https?://(www\.)?", "", payload.get("source_url", "")).split("/")[0])
    if payload.get("benefit_note"):
        item["attributes"] = {"benefit_note": payload["benefit_note"]}
    item.pop("benefit_note", None)
    return item


def pending_documents(db: Session, limit: int) -> list[RawDocument]:
    done = select(Candidate.raw_document_id).where(Candidate.raw_document_id.is_not(None))
    return list(db.scalars(select(RawDocument).where(RawDocument.id.not_in(done)).limit(limit)))


def run(limit: int = 10) -> dict[str, int]:
    init_db()
    db = SessionLocal()
    stats: dict[str, int] = {}
    try:
        for doc in pending_documents(db, limit):
            c = extract_document(db, doc)
            stats[c.status] = stats.get(c.status, 0) + 1
            log.info("%s → %s %s", doc.url, c.status, (c.payload or {}).get("title", c.reject_reason or ""))
    finally:
        db.close()
    return stats


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    log.info("итог: %s", run(ap.parse_args().limit))


if __name__ == "__main__":
    main()
