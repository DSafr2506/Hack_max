"""Эндпоинты, завязанные на MAX: вход, профиль, участие, календарь, переходы, демо-напоминание, шеринг."""

import logging
from datetime import date, datetime, timedelta

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import catalog, ics, logic, maxapi
from app.config import settings
from app.db import get_db
from app.models import CalendarItem, Event, Participation, ShareLink, User, utcnow
from app.schemas import (
    CalendarItemOut,
    DemoReminderIn,
    LaunchIn,
    LaunchOut,
    ParticipationIn,
    ParticipationOut,
    ParticipationPatch,
    ProfileIn,
    ShareOut,
    UserOut,
)

log = logging.getLogger("app.api")
router = APIRouter()


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(status_code=status, detail={"code": code, "message": message or code})


# ─────────────────────────── JWT ───────────────────────────


def issue_token(user: User) -> str:
    payload = {"sub": str(user.id), "exp": utcnow() + timedelta(days=settings.jwt_ttl_days)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _user_from_token(db: Session, token: str) -> User | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return db.get(User, int(payload["sub"]))


def optional_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return _user_from_token(db, authorization.split(" ", 1)[1])


def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise ApiError(401, "unauthorized")
    return user


def csv_list(value: str) -> list[str]:
    return [x for x in value.split(",") if x]


def to_csv(items: list[str]) -> str:
    return "," + ",".join(items) + "," if items else ""


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        role=u.role,
        region_code=u.region_code,
        city=u.city,
        grade=u.grade,
        type_codes=csv_list(u.type_codes),
        goal_codes=csv_list(u.goal_codes),
        subject_codes=csv_list(u.subject_codes),
        notifications_enabled=u.notifications_enabled,
        onboarded=u.onboarded,
    )


# ─────────────────────────── вход через MAX ───────────────────────────


@router.post("/api/auth/launch", response_model=LaunchOut)
def auth_launch(body: LaunchIn, db: Session = Depends(get_db)) -> LaunchOut:
    if body.init_data:
        try:
            data = maxapi.verify_init_data(body.init_data, settings.max_bot_token)
        except maxapi.AuthError as exc:
            log.info("launch отклонён: %s", exc.code)  # саму init_data не логируем
            raise ApiError(401, "unauthorized", exc.code) from None
        external_id, start_param = data["external_id"], data["start_param"]
    elif body.dev_user_id and settings.dev_fake_auth:
        external_id, start_param = f"dev:{body.dev_user_id}", None
    else:
        raise ApiError(401, "unauthorized", "init_data required")

    user, is_new = logic.launch_user(db, external_id, start_param)
    return LaunchOut(token=issue_token(user), user=user_out(user), is_new=is_new, start_param=start_param)


@router.get("/api/me", response_model=UserOut)
def get_me(user: User = Depends(current_user)) -> UserOut:
    return user_out(user)


def _check_codes(group: str, values: list[str] | None) -> None:
    unknown = set(values or []) - catalog.codes(group)
    if unknown:
        raise ApiError(422, "validation_error", f"unknown {group}: {sorted(unknown)}")


def _apply_profile(db: Session, user: User, body: ProfileIn) -> None:
    for group, values in (("type", body.type_codes), ("goal", body.goal_codes), ("subject", body.subject_codes)):
        _check_codes(group, values)
    if body.city is not None:
        city = next((c for c in catalog.dicts()["city"] if c["name"] == body.city), None)
        if city is None:
            raise ApiError(422, "validation_error", "unknown city")
        user.city, user.region_code = city["name"], city["region_code"]
    if body.region_code is not None:
        if body.region_code not in catalog.codes("region"):
            raise ApiError(422, "validation_error", "unknown region_code")
        user.region_code = body.region_code
    if body.grade is not None:
        user.grade = body.grade
    if body.type_codes is not None:
        user.type_codes = to_csv(body.type_codes)
    if body.goal_codes is not None:
        user.goal_codes = to_csv(body.goal_codes)
    if body.subject_codes is not None:
        user.subject_codes = to_csv(body.subject_codes)


@router.patch("/api/me", response_model=UserOut)
def patch_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserOut:
    _apply_profile(db, user, body)
    db.commit()
    return user_out(user)


@router.post("/api/me/onboarding", response_model=UserOut)
def onboarding(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)) -> UserOut:
    _apply_profile(db, user, body)
    user.onboarded = True
    db.commit()
    return user_out(user)


# ─────────────────────────── участие ───────────────────────────


def _published_event(db: Session, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None or event.status != "published":
        raise ApiError(404, "not_found", "event_not_found")
    return event


def _p_out(p: Participation) -> ParticipationOut:
    return ParticipationOut(id=p.id, event_id=p.event_id, status=p.status, updated_at=p.updated_at)


@router.get("/api/me/participations", response_model=list[ParticipationOut])
def list_participations(
    status: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ParticipationOut]:
    q = select(Participation).where(Participation.user_id == user.id)
    if status:
        q = q.where(Participation.status == status)
    return [_p_out(p) for p in db.scalars(q.order_by(Participation.updated_at.desc()))]


@router.post("/api/me/participations", response_model=ParticipationOut)
def upsert_participation(
    body: ParticipationIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ParticipationOut:
    if body.status not in logic.PARTICIPATION_STATUSES:
        raise ApiError(422, "validation_error", "bad status")
    event = _published_event(db, body.event_id)
    return _p_out(logic.set_participation(db, user, event, body.status))


@router.patch("/api/me/participations/{pid}", response_model=ParticipationOut)
def patch_participation(
    pid: int, body: ParticipationPatch, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ParticipationOut:
    p = db.get(Participation, pid)
    if p is None:
        raise ApiError(404, "not_found")
    if p.user_id != user.id:
        raise ApiError(403, "forbidden")
    if body.status not in logic.PARTICIPATION_STATUSES:
        raise ApiError(422, "validation_error", "bad status")
    event = db.get(Event, p.event_id)
    return _p_out(logic.set_participation(db, user, event, body.status))


@router.get("/api/me/calendar", response_model=list[CalendarItemOut])
def my_calendar(
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[CalendarItemOut]:
    q = (
        select(CalendarItem, Event)
        .join(Event, Event.id == CalendarItem.event_id)
        .join(
            Participation,
            (Participation.event_id == CalendarItem.event_id) & (Participation.user_id == user.id),
        )
        .where(CalendarItem.user_id == user.id, Participation.status == "going")
    )
    if from_:
        q = q.where(CalendarItem.at >= from_)
    if to:
        q = q.where(CalendarItem.at <= to)
    return [
        CalendarItemOut(event_id=c.event_id, slug=e.slug, type=e.type, kind=c.kind, at=c.at, title=e.title)
        for c, e in db.execute(q.order_by(CalendarItem.at))
    ]


# ─────────────────────────── переход к организатору ───────────────────────────


@router.get("/go/{event_id}")
def go(
    event_id: int,
    src: str = "card",
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    event = _published_event(db, event_id)
    if not event.registration_url:
        raise ApiError(404, "no_external_link", "Регистрация через школу — спроси учителя предмета")
    logic.record_click(db, event, user.id if user else None, src)
    return RedirectResponse(event.registration_url, status_code=302)


# ─────────────────────────── демо ───────────────────────────


@router.post("/api/demo/fire-reminder")
def demo_fire_reminder(
    body: DemoReminderIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    event = _published_event(db, body.event_id)
    if not user.notifications_enabled:
        # на сцене напоминание должно прийти: включаем обратно явно
        user.notifications_enabled = True
    r = logic.fire_demo_reminder(db, user, event, body.delay_seconds)
    return {"reminder_id": r.id, "scheduled_at": r.scheduled_at}


# ─────────────────────────── шеринг ───────────────────────────


@router.get("/api/events/{slug}/share", response_model=ShareOut)
def share_event(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> ShareOut:
    event = db.scalar(select(Event).where(Event.slug == slug, Event.status == "published"))
    if event is None:
        raise ApiError(404, "not_found", "event_not_found")
    link = logic.get_or_create_share(db, "ev", event.id, user.id)
    dl = logic.deep_link(link.token)
    text = f"{event.title}\n{dl}"
    return ShareOut(token=link.token, deep_link=dl, share_url=logic.share_url(text), share_text=text)


@router.post("/api/share/{token}/open")
def share_open(token: str, db: Session = Depends(get_db)) -> dict:
    link = db.scalar(select(ShareLink).where(ShareLink.token == token))
    if link is None:
        raise ApiError(404, "not_found")
    link.opens += 1
    db.commit()
    return {"kind": link.kind, "ref_id": link.ref_id}


# ─────────────────────────── вебхук MAX (прод) ───────────────────────────


@router.post(maxapi.WEBHOOK_PATH, include_in_schema=False)
def max_webhook(
    update: dict,
    background: BackgroundTasks,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict:
    """MAX ждёт 200 за 30 секунд, поэтому обработка уходит в фон."""
    if not maxapi.check_webhook_secret(x_max_bot_api_secret):
        raise ApiError(401, "unauthorized")
    background.add_task(logic.handle_update, update)
    return {"ok": True}


# ─────────────────────────── каталог (H2) ───────────────────────────


def _split(values: list[str] | None) -> list[str]:
    """Списки принимаем и как ?types=a,b, и как ?types=a&types=b."""
    return [v for raw in values or [] for v in raw.split(",") if v]


def event_filter(
    types: list[str] | None = Query(default=None),
    goals: list[str] | None = Query(default=None),
    subjects: list[str] | None = Query(default=None),
    grade: int | None = None,
    region_code: str | None = None,
    available_from_region: bool = False,
    format: str | None = None,
    price_kinds: list[str] | None = Query(default=None),
    travel_covered: bool = False,
    entry_kinds: list[str] | None = Query(default=None),
    levels: list[str] | None = Query(default=None),
    deadline_before: date | None = None,
    only_with_deadline: bool = False,
    q: str | None = None,
    sort: str = "deadline",
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> catalog.EventFilter:
    return catalog.EventFilter(
        types=_split(types),
        goals=_split(goals),
        subjects=_split(subjects),
        grade=grade,
        region_code=region_code,
        available_from_region=available_from_region,
        format=format,
        price_kinds=_split(price_kinds),
        travel_covered=travel_covered,
        entry_kinds=_split(entry_kinds),
        levels=_split(levels),
        deadline_before=deadline_before,
        only_with_deadline=only_with_deadline,
        q=q or None,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/api/dicts")
def get_dicts() -> dict:
    return catalog.dicts()


@router.get("/api/events")
def list_events(
    f: catalog.EventFilter = Depends(event_filter),
    detail: str = "short",
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> dict:
    items, total = catalog.search(db, f)
    statuses = catalog.my_statuses(db, user.id if user else None, [e.id for e in items])
    return {
        # detail=full — для фронта, который фильтрует каталог у себя и сразу показывает карточку
        "items": [
            (catalog.event_full if detail == "full" else catalog.event_short)(e, statuses.get(e.id)) for e in items
        ],
        "total": total,
        "has_more": f.offset + len(items) < total,
    }


def _event_by_slug(db: Session, slug: str) -> Event:
    event = db.scalar(select(Event).where(Event.slug == slug, Event.status == "published"))
    if event is None:
        raise ApiError(404, "not_found", "event_not_found")
    return event


@router.get("/api/events/{slug}.ics")
def event_ics(slug: str, db: Session = Depends(get_db)) -> Response:
    event = _event_by_slug(db, slug)
    return Response(
        ics.calendar([event], event.title),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{event.slug}.ics"'},
    )


@router.get("/api/me/calendar.ics")
def my_calendar_ics(token: str, db: Session = Depends(get_db)) -> Response:
    """Токен в query: WebApp.downloadFile не умеет передавать заголовки."""
    user = _user_from_token(db, token)
    if user is None:
        raise ApiError(401, "unauthorized")
    events = db.scalars(
        select(Event)
        .join(Participation, Participation.event_id == Event.id)
        .where(Participation.user_id == user.id, Participation.status == "going")
    ).all()
    return Response(
        ics.calendar(list(events), "Мои даты"),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="my-dates.ics"'},
    )


@router.get("/api/events/{slug}/calendar-links")
def event_calendar_links(slug: str, db: Session = Depends(get_db)) -> dict:
    event = _event_by_slug(db, slug)
    return {
        "ics_url": f"{settings.public_url.rstrip('/')}/api/events/{event.slug}.ics",
        "google": ics.google_link(event),
    }


@router.get("/api/events/{slug}/similar")
def event_similar(slug: str, db: Session = Depends(get_db)) -> list[dict]:
    return [catalog.event_short(e) for e in catalog.similar(db, _event_by_slug(db, slug))]


@router.get("/api/events/{slug}")
def event_card(slug: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)) -> dict:
    event = _event_by_slug(db, slug)
    status = catalog.my_statuses(db, user.id if user else None, [event.id]).get(event.id)
    return catalog.event_full(event, status)


@router.get("/api/events/by-id/{event_id}")
def event_card_by_id(event_id: int, db: Session = Depends(get_db)) -> dict:
    """Для диплинка e_<id> из кнопки бота: фронт узнаёт slug и открывает карточку."""
    return catalog.event_full(_published_event(db, event_id))
