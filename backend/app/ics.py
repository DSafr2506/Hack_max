"""Генерация .ics (RFC 5545) и ссылок «добавить в Google Календарь»."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit

from app.config import settings
from app.models import Event


def _fmt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def _fold(line: str) -> list[str]:
    """Строки длиннее 75 октетов переносятся (RFC 5545, 3.1)."""
    out, current = [], ""
    for ch in line:
        if len((current + ch).encode()) > 75:
            out.append(current)
            current = " " + ch
        else:
            current += ch
    out.append(current)
    return out


def _host() -> str:
    return urlsplit(settings.public_url).hostname or "localhost"


def _public(path: str) -> str:
    return settings.public_url.rstrip("/") + path


def event_blocks(e: Event, now: datetime | None = None) -> list[list[str]]:
    now = now or datetime.now(timezone.utc)
    desc = (e.short_description or "") + f"\nИсточник: {e.source_url}"
    go = _public(f"/go/{e.id}?src=card")
    blocks = []
    if e.starts_at:
        end = e.ends_at or e.starts_at + timedelta(hours=2)
        blocks.append(
            [
                "BEGIN:VEVENT",
                f"UID:event-{e.id}@{_host()}",
                f"DTSTAMP:{_fmt(now)}",
                f"DTSTART:{_fmt(e.starts_at)}",
                f"DTEND:{_fmt(end)}",
                f"SUMMARY:{_escape(e.title)}",
                f"DESCRIPTION:{_escape(desc)}",
                f"URL:{go}",
                "BEGIN:VALARM",
                "TRIGGER:-PT24H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape('Завтра: ' + e.title)}",
                "END:VALARM",
                "END:VEVENT",
            ]
        )
    if e.registration_deadline:
        d = e.registration_deadline
        blocks.append(
            [
                "BEGIN:VEVENT",
                f"UID:event-{e.id}-deadline@{_host()}",
                f"DTSTAMP:{_fmt(now)}",
                f"DTSTART:{_fmt(d - timedelta(hours=1))}",
                f"DTEND:{_fmt(d)}",
                f"SUMMARY:{_escape('Дедлайн регистрации: ' + e.title)}",
                f"DESCRIPTION:{_escape(desc)}",
                f"URL:{go}",
                "BEGIN:VALARM",
                "TRIGGER:-PT24H",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape('Завтра дедлайн: ' + e.title)}",
                "END:VALARM",
                "END:VEVENT",
            ]
        )
    return blocks


def calendar(events: list[Event], name: str = "Возможности") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//agregator-vozmozhnostey//RU",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for e in events:
        for block in event_blocks(e):
            lines.extend(block)
    lines.append("END:VCALENDAR")
    folded = [part for line in lines for part in _fold(line)]
    return "\r\n".join(folded) + "\r\n"


def google_link(e: Event) -> str | None:
    start = e.starts_at or (e.registration_deadline - timedelta(hours=1) if e.registration_deadline else None)
    if start is None:
        return None
    end = e.ends_at or (e.registration_deadline if not e.starts_at else start + timedelta(hours=2))
    title = e.title if e.starts_at else f"Дедлайн регистрации: {e.title}"
    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{_fmt(start)}/{_fmt(end)}",
        "details": f"{e.short_description}\n{_public(f'/go/{e.id}?src=card')}",
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(params)
