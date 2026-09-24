"""Бизнес-логика, связанная с MAX: пользователи, участие, календарь, напоминания, обработка апдейтов бота."""

import base64
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import maxapi
from app.config import settings
from app.db import SessionLocal
from app.models import (
    BotState,
    CalendarItem,
    Click,
    Event,
    Participation,
    Reminder,
    ShareLink,
    User,
    utcnow,
)

log = logging.getLogger("app.logic")

MSK = timezone(timedelta(hours=3))
QUIET_FROM, QUIET_TO = 22, 8  # тихие часы по МСК
MAX_ATTEMPTS = 3
PARTICIPATION_STATUSES = ("interested", "going", "participated", "skipped")
SHARE_PREFIXES = ("ev", "col", "cls")


# ─────────────────────────── пользователи ───────────────────────────


def get_or_create_user(db: Session, external_id: str) -> tuple[User, bool]:
    user = db.scalar(select(User).where(User.external_id == external_id))
    if user:
        return user, False
    user = User(external_id=external_id)
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # параллельный первый вход того же пользователя (двойной запрос) — берём уже созданного
        db.rollback()
        existing = db.scalar(select(User).where(User.external_id == external_id))
        if existing is None:
            raise
        return existing, False
    return user, True


def launch_user(db: Session, external_id: str, start_param: str | None) -> tuple[User, bool]:
    """Вход из мини-приложения: upsert пользователя + атрибуция по токену шеринга."""
    user, is_new = get_or_create_user(db, external_id)
    user.last_seen_at = utcnow()
    if is_new and start_param and start_param.split("_", 1)[0] in SHARE_PREFIXES:
        link = db.scalar(select(ShareLink).where(ShareLink.token == start_param))
        if link:
            user.acquisition_token = link.token
            link.signups += 1
    db.commit()
    return user, is_new


def set_notifications(db: Session, user: User, enabled: bool) -> None:
    user.notifications_enabled = enabled
    if not enabled:
        for r in db.scalars(
            select(Reminder).where(Reminder.user_id == user.id, Reminder.status == "pending")
        ):
            r.status = "skipped"
    db.commit()


# ─────────────────────────── участие и календарь ───────────────────────────


def set_participation(db: Session, user: User, event: Event, status: str) -> Participation:
    if status not in PARTICIPATION_STATUSES:
        raise ValueError(f"unknown status {status}")
    p = db.scalar(
        select(Participation).where(Participation.user_id == user.id, Participation.event_id == event.id)
    )
    if p is None:
        p = Participation(user_id=user.id, event_id=event.id, status=status)
        db.add(p)
    else:
        p.status = status
    db.flush()
    if status == "going":
        add_to_calendar(db, user, event)
        schedule_reminders(db, user, event)
    elif status == "skipped":
        cancel_reminders(db, user, event, keep_followup=False)
    elif status == "participated":
        cancel_reminders(db, user, event, keep_followup=False)
    db.commit()
    return p


def add_to_calendar(db: Session, user: User, event: Event) -> None:
    for kind, at in (("deadline", event.registration_deadline), ("start", event.starts_at)):
        if at is None:
            continue
        exists = db.scalar(
            select(CalendarItem).where(
                CalendarItem.user_id == user.id, CalendarItem.event_id == event.id, CalendarItem.kind == kind
            )
        )
        if exists:
            exists.at = at
        else:
            db.add(CalendarItem(user_id=user.id, event_id=event.id, kind=kind, at=at))


def reminder_plan(event: Event) -> list[tuple[str, datetime]]:
    plan: list[tuple[str, datetime]] = []
    if event.registration_deadline:
        plan.append(("deadline_3d", event.registration_deadline - timedelta(days=3)))
        plan.append(("deadline_1d", event.registration_deadline - timedelta(days=1)))
    if event.starts_at:
        plan.append(("start_1d", event.starts_at - timedelta(days=1)))
    anchor = event.ends_at or event.starts_at
    if anchor:
        plan.append(("followup", anchor + timedelta(days=2)))
    return plan


def upsert_reminder(db: Session, user: User, event: Event, kind: str, at: datetime) -> Reminder:
    key = f"{user.id}:{event.id}:{kind}"
    r = db.scalar(select(Reminder).where(Reminder.dedup_key == key))
    if r is None:
        r = Reminder(user_id=user.id, event_id=event.id, kind=kind, scheduled_at=at, dedup_key=key)
        db.add(r)
    elif r.status != "sent" or kind == "demo":
        r.scheduled_at, r.status, r.attempts = at, "pending", 0
    return r


def schedule_reminders(db: Session, user: User, event: Event) -> list[Reminder]:
    now = utcnow()
    created = [upsert_reminder(db, user, event, kind, at) for kind, at in reminder_plan(event) if at > now]
    db.flush()
    return created


def cancel_reminders(db: Session, user: User, event: Event, keep_followup: bool) -> None:
    for r in db.scalars(
        select(Reminder).where(
            Reminder.user_id == user.id, Reminder.event_id == event.id, Reminder.status == "pending"
        )
    ):
        if keep_followup and r.kind == "followup":
            continue
        r.status = "skipped"


def fire_demo_reminder(db: Session, user: User, event: Event, delay_seconds: int = 10) -> Reminder:
    r = upsert_reminder(db, user, event, "demo", utcnow() + timedelta(seconds=delay_seconds))
    db.commit()
    return r


# ─────────────────────────── отправка напоминаний ───────────────────────────


def in_quiet_hours(now: datetime) -> bool:
    hour = now.astimezone(MSK).hour
    return hour >= QUIET_FROM or hour < QUIET_TO


def next_morning(now: datetime) -> datetime:
    local = now.astimezone(MSK)
    morning = local.replace(hour=QUIET_TO, minute=0, second=0, microsecond=0)
    if local.hour >= QUIET_TO:
        morning += timedelta(days=1)
    return morning.astimezone(timezone.utc)


def fmt_msk(dt: datetime) -> str:
    return dt.astimezone(MSK).strftime("%d.%m.%Y %H:%M") + " МСК"


def go_url(event_id: int, src: str) -> str:
    return f"{settings.public_url.rstrip('/')}/go/{event_id}?src={src}"


def render_reminder(r: Reminder) -> str:
    e = r.event
    title = f"**{e.title}**"
    if r.kind in ("deadline_3d", "deadline_1d") and e.registration_deadline:
        when = "через 3 дня" if r.kind == "deadline_3d" else "завтра"
        return f"Регистрация {when} закрывается: {title}\nДедлайн: {fmt_msk(e.registration_deadline)}"
    if r.kind == "start_1d" and e.starts_at:
        return f"Завтра начинается {title}\nСтарт: {fmt_msk(e.starts_at)}"
    if r.kind == "followup":
        return f"Получилось поучаствовать в {title}?"
    # demo и всё остальное
    parts = [f"Напоминание: {title}"]
    if e.registration_deadline:
        parts.append(f"Дедлайн регистрации: {fmt_msk(e.registration_deadline)}")
    elif e.starts_at:
        parts.append(f"Старт: {fmt_msk(e.starts_at)}")
    return "\n".join(parts)


def buttons_for(r: Reminder) -> list[list[dict[str, Any]]]:
    e = r.event
    if r.kind == "followup":
        return [
            [
                maxapi.btn_callback("Да, участвовал", f"fu:{e.id}:participated", "positive"),
                maxapi.btn_callback("Нет", f"fu:{e.id}:skipped"),
            ]
        ]
    rows: list[list[dict[str, Any]]] = []
    if e.registration_url:
        rows.append([maxapi.btn_link("Перейти к регистрации", go_url(e.id, "reminder"))])
    rows.append([maxapi.btn_open_app("Открыть карточку", f"e_{e.id}")])
    rows.append(
        [
            maxapi.btn_callback("Напомнить завтра", f"snz:{r.id}"),
            maxapi.btn_callback("Информация устарела", f"stale:{e.id}"),
        ]
    )
    return rows


def dispatch_reminders(db: Session, limit: int = 50) -> int:
    """Вызывается планировщиком раз в 30 секунд. Возвращает число отправленных."""
    now = utcnow()
    rows = db.scalars(
        select(Reminder)
        .where(Reminder.status == "pending", Reminder.scheduled_at <= now)
        .order_by(Reminder.scheduled_at)
        .limit(limit)
    ).all()
    sent = 0
    for r in rows:
        if not r.user.notifications_enabled:
            r.status = "skipped"
            db.commit()
            continue
        if r.kind != "demo" and in_quiet_hours(now):
            r.scheduled_at = next_morning(now)
            db.commit()
            continue
        result = maxapi.get_client().send_message(
            r.user.external_id, render_reminder(r), buttons_for(r), notify=not r.user.dialog_muted
        )
        r.attempts += 1
        if result.ok:
            r.status, r.sent_at = "sent", utcnow()
            sent += 1
        elif result.status in (403, 404):
            # пользователь заблокировал бота или не начинал с ним диалог
            log.info("MAX: доставка невозможна (%s), напоминания пользователя гасим", result.error)
            r.status = "failed"
            set_notifications(db, r.user, False)
        elif r.attempts >= MAX_ATTEMPTS:
            r.status = "failed"
        else:
            r.scheduled_at = utcnow() + timedelta(minutes=5 * r.attempts)
        db.commit()
    return sent


def run_dispatch_job() -> None:
    db = SessionLocal()
    try:
        dispatch_reminders(db)
    except Exception:
        log.exception("ошибка рассылки напоминаний")
    finally:
        db.close()


# ─────────────────────────── обработка апдейтов бота ───────────────────────────


WELCOME = (
    "Привет! Здесь олимпиады, смены, хакатоны и профпробы для школьников — "
    "с учётом твоего региона и класса.\n\n"
    "Отметь «Участвую» в карточке — я напомню о дедлайне."
)


def send_welcome(external_id: str, payload: str | None = None) -> None:
    maxapi.get_client().send_message(
        external_id, WELCOME, [[maxapi.btn_open_app("Открыть подборку", payload)]]
    )


def handle_update(update: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        _handle_update(db, update)
    finally:
        db.close()


def _handle_update(db: Session, update: dict[str, Any]) -> None:
    kind = update.get("update_type")
    external_id = maxapi.update_user_id(update)
    if not external_id:
        log.debug("MAX: апдейт %s без user_id, пропуск", kind)
        return

    if kind == "bot_started":
        user, _ = get_or_create_user(db, external_id)
        set_notifications(db, user, True)
        send_welcome(external_id, _safe_payload(update.get("payload")))
    elif kind in ("bot_stopped", "dialog_removed"):
        user = db.scalar(select(User).where(User.external_id == external_id))
        if user:
            set_notifications(db, user, False)
    elif kind in ("dialog_muted", "dialog_unmuted"):
        user = db.scalar(select(User).where(User.external_id == external_id))
        if user:
            user.dialog_muted = kind == "dialog_muted"
            db.commit()
    elif kind == "message_created":
        text = (((update.get("message") or {}).get("body") or {}).get("text") or "").strip()
        if text.split(" ", 1)[0].lower() in ("/start", "старт"):
            user, _ = get_or_create_user(db, external_id)
            set_notifications(db, user, True)
            send_welcome(external_id)
    elif kind == "message_callback":
        handle_callback(db, external_id, update.get("callback") or {})


def _safe_payload(payload: str | None) -> str | None:
    if not payload:
        return None
    ok = all(c.isascii() and (c.isalnum() or c in "_-") for c in payload)
    return payload[:512] if ok else None


def handle_callback(db: Session, external_id: str, callback: dict[str, Any]) -> None:
    client = maxapi.get_client()
    callback_id = callback.get("callback_id", "")
    payload = callback.get("payload") or ""
    action, _, rest = payload.partition(":")
    user, _ = get_or_create_user(db, external_id)
    db.commit()

    if action == "fu":  # followup: fu:<event_id>:<status>
        event_id_s, _, status = rest.partition(":")
        event = db.get(Event, int(event_id_s)) if event_id_s.isdigit() else None
        if event is None or status not in ("participated", "skipped"):
            client.answer_callback(callback_id, "Кнопка устарела")
            return
        set_participation(db, user, event, status)
        text = "Круто, отметили участие!" if status == "participated" else "Понял, отметили. В следующий раз получится!"
        client.answer_callback(callback_id, "Сохранено", new_text=f"{text}\n**{event.title}**")

    elif action == "snz":  # «напомнить завтра»: snz:<reminder_id>
        r = db.get(Reminder, int(rest)) if rest.isdigit() else None
        if r is None or r.user_id != user.id:
            client.answer_callback(callback_id, "Кнопка устарела")
            return
        snooze = Reminder(
            user_id=user.id,
            event_id=r.event_id,
            kind="snooze",
            scheduled_at=utcnow() + timedelta(days=1),
            dedup_key=f"{user.id}:{r.event_id}:snooze:{r.id}",
        )
        if db.scalar(select(Reminder).where(Reminder.dedup_key == snooze.dedup_key)) is None:
            db.add(snooze)
            db.commit()
        client.answer_callback(callback_id, "Напомню завтра")

    elif action == "stale":  # «информация устарела»: stale:<event_id>
        event = db.get(Event, int(rest)) if rest.isdigit() else None
        if event is not None:
            event.freshness = "reported"
            db.commit()
        client.answer_callback(callback_id, "Спасибо! Модератор перепроверит карточку")

    else:
        log.info("MAX: неизвестный callback payload %r", payload[:40])
        client.answer_callback(callback_id, "Кнопка устарела")


# ─────────────────────────── переходы и шеринг ───────────────────────────


def record_click(db: Session, event: Event, user_id: int | None, source: str) -> None:
    if source not in ("feed", "card", "reminder", "share"):
        source = "card"
    db.add(Click(user_id=user_id, event_id=event.id, source=source))
    db.commit()


def new_share_token(kind: str) -> str:
    """16 случайных байт, base64url без padding: алфавит A-Za-z0-9_- (требование MAX к payload)."""
    raw = base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode()
    return f"{kind}_{raw}"


def deep_link(payload: str) -> str:
    return f"https://max.ru/{settings.max_bot_name}?startapp={payload}"


def share_url(text: str) -> str:
    return f"https://max.ru/:share?text={quote(text, safe='')}"


def get_or_create_share(db: Session, kind: str, ref_id: int, created_by: int | None) -> ShareLink:
    link = db.scalar(
        select(ShareLink).where(
            ShareLink.kind == kind, ShareLink.ref_id == ref_id, ShareLink.created_by == created_by
        )
    )
    if link is None:
        link = ShareLink(token=new_share_token(kind), kind=kind, ref_id=ref_id, created_by=created_by)
        db.add(link)
        db.commit()
    return link


# ─────────────────────────── маркер long polling ───────────────────────────


def load_marker() -> int | None:
    db = SessionLocal()
    try:
        row = db.get(BotState, "updates_marker")
        return int(row.value) if row else None
    finally:
        db.close()


def save_marker(marker: int) -> None:
    db = SessionLocal()
    try:
        row = db.get(BotState, "updates_marker")
        if row:
            row.value = str(marker)
        else:
            db.add(BotState(key="updates_marker", value=str(marker)))
        db.commit()
    finally:
        db.close()
