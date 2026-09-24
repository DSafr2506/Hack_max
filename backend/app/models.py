from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """SQLite теряет таймзону: пишем наивный UTC, читаем timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime запрещён, используйте UTC-aware")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(300))
    short_description: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    organizer: Mapped[str] = mapped_column(String(300), default="")
    organizer_kind: Mapped[str] = mapped_column(String(32), default="other")

    format: Mapped[str] = mapped_column(String(16), default="online")
    region_codes: Mapped[str] = mapped_column(String(500), default="")
    is_federal: Mapped[bool] = mapped_column(Boolean, default=False)
    venue_city: Mapped[str | None] = mapped_column(String(200))

    grade_min: Mapped[int | None] = mapped_column(Integer)
    grade_max: Mapped[int | None] = mapped_column(Integer)
    participation: Mapped[str] = mapped_column(String(16), default="individual")

    registration_deadline: Mapped[datetime | None] = mapped_column(UTCDateTime)
    starts_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    price_kind: Mapped[str] = mapped_column(String(16), default="unknown")
    travel_covered: Mapped[str] = mapped_column(String(16), default="unknown")
    accommodation_covered: Mapped[str] = mapped_column(String(16), default="unknown")

    entry_kind: Mapped[str] = mapped_column(String(16), default="open")
    selection_note: Mapped[str | None] = mapped_column(Text)
    registration_url: Mapped[str | None] = mapped_column(String(1000))
    registration_channel: Mapped[str] = mapped_column(String(16), default="external")

    level: Mapped[str | None] = mapped_column(String(16))
    goal_codes: Mapped[str] = mapped_column(String(300), default="")
    subject_codes: Mapped[str] = mapped_column(String(500), default="")
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)

    source_url: Mapped[str] = mapped_column(String(1000))
    source_name: Mapped[str] = mapped_column(String(300), default="")
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    freshness: Mapped[str] = mapped_column(String(16), default="fresh")

    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # user.id из MAX. Больше ничего из профиля MAX не храним.
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(16), default="student")
    region_code: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(100))
    grade: Mapped[int | None] = mapped_column(Integer)
    type_codes: Mapped[str] = mapped_column(String(300), default="")
    goal_codes: Mapped[str] = mapped_column(String(300), default="")
    subject_codes: Mapped[str] = mapped_column(String(500), default="")
    # гасится событиями bot_stopped / dialog_removed и ответом 403/404 при отправке,
    # включается bot_started и /start
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    dialog_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    acquisition_token: Mapped[str | None] = mapped_column(String(64))
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (UniqueConstraint("user_id", "event_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class CalendarItem(Base):
    __tablename__ = "calendar_items"
    __table_args__ = (UniqueConstraint("user_id", "event_id", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    kind: Mapped[str] = mapped_column(String(16))
    at: Mapped[datetime] = mapped_column(UTCDateTime)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    kind: Mapped[str] = mapped_column(String(16))
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dedup_key: Mapped[str] = mapped_column(String(200), unique=True)

    user: Mapped[User] = relationship()
    event: Mapped[Event] = relationship()


class ShareLink(Base):
    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    kind: Mapped[str] = mapped_column(String(8))
    ref_id: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[int | None] = mapped_column(Integer)
    opens: Mapped[int] = mapped_column(Integer, default=0)
    signups: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    source: Mapped[str] = mapped_column(String(16), default="card")


class BotState(Base):
    """Ключ-значение для состояния бота: маркер long polling и т.п."""

    __tablename__ = "bot_state"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(1000))
    kind: Mapped[str] = mapped_column(String(32))
    region_code: Mapped[str | None] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_status: Mapped[str | None] = mapped_column(String(64))


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    url: Mapped[str] = mapped_column(String(1000))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True)
    text: Mapped[str] = mapped_column(Text)


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_document_id: Mapped[int | None] = mapped_column(ForeignKey("raw_documents.id"))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="new")
    event_id: Mapped[int | None] = mapped_column(Integer)
    model_name: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    reject_reason: Mapped[str | None] = mapped_column(Text)
