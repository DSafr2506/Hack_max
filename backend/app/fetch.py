"""Сбор страниц источников в raw_documents (модуль H8.2).

Правила: уважаем robots.txt, пауза между запросами к одному домену, честный User-Agent,
content_hash защищает от повторной обработки. Сырой текст храним, чтобы переизвлекать новым промптом без обхода.
Запуск: python -m app.fetch --limit 10
"""

import argparse
import hashlib
import logging
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import DATA_DIR
from app.db import SessionLocal, init_db
from app.models import RawDocument, Source, utcnow

log = logging.getLogger("app.fetch")
USER_AGENT = "AgregatorVozmozhnostey/0.1 (hackathon project; школьный навигатор мероприятий)"
DELAY = 1.5
SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}
BLOCK_TAGS = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "tr", "section", "article", "td", "dt", "dd"}


class _Extractor(HTMLParser):
    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.parts: list[str] = []
        self.links: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIP_TAGS:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                self.links.append(urljoin(self.base, href))
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIP_TAGS and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        if not self.skip:
            self.parts.append(data)


def html_to_text(html: str, base: str = "") -> tuple[str, list[str], str]:
    p = _Extractor(base)
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text, p.links, p.title.strip()


class Fetcher:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.http = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
        self.robots: dict[str, RobotFileParser] = {}
        self.last_hit: dict[str, float] = {}

    def allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self.robots:
            rp = RobotFileParser()
            try:
                r = self.http.get(f"{host}/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self.robots[host] = rp
        return self.robots[host].can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self.allowed(url):
            log.info("robots.txt запрещает %s", url)
            return None
        host = urlsplit(url).netloc
        wait = DELAY - (time.monotonic() - self.last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        self.last_hit[host] = time.monotonic()
        try:
            r = self.http.get(url)
        except httpx.HTTPError as exc:
            log.warning("%s: %s", url, type(exc).__name__)
            return None
        if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
            log.warning("%s: HTTP %s", url, r.status_code)
            return None
        return r.text


def save_document(db: Session, source: Source | None, url: str, text: str) -> RawDocument | None:
    digest = hashlib.sha256(text.encode()).hexdigest()
    if db.scalar(select(RawDocument).where(RawDocument.content_hash == digest)):
        return None  # уже обработанная страница
    doc = RawDocument(source_id=source.id if source else None, url=url, text=text, content_hash=digest)
    db.add(doc)
    db.commit()
    return doc


def sync_sources(db: Session, path: Path | None = None) -> list[Source]:
    items: list[dict[str, Any]] = yaml.safe_load((path or DATA_DIR / "sources.yaml").read_text(encoding="utf-8")) or []
    result = []
    for it in items:
        src = db.scalar(select(Source).where(Source.url == it["url"]))
        if src is None:
            src = Source(url=it["url"])
            db.add(src)
        src.name, src.kind = it["name"], it.get("kind", "single_page")
        src.region_code, src.link_pattern = it.get("region_code"), it.get("link_pattern")
        src.is_active = it.get("active", True)
        result.append(src)
    db.commit()
    return [s for s in result if s.is_active]


def fetch_source(db: Session, f: Fetcher, src: Source, limit: int) -> int:
    html = f.get(src.url)
    if html is None:
        src.last_status = "error"
        src.last_run_at = utcnow()
        db.commit()
        return 0
    text, links, _ = html_to_text(html, src.url)
    saved = 0
    if src.kind == "single_page":
        saved += save_document(db, src, src.url, text) is not None
    elif src.kind == "html_list":
        pattern = re.compile(src.link_pattern or ".")
        seen: set[str] = set()
        for link in links:
            if saved >= limit or link in seen or not pattern.search(link):
                continue
            seen.add(link)
            page = f.get(link)
            if page:
                saved += save_document(db, src, link, html_to_text(page, link)[0]) is not None
    src.last_status, src.last_run_at = f"ok:{saved}", utcnow()
    db.commit()
    return saved


def run(limit: int = 10) -> int:
    init_db()
    db = SessionLocal()
    f = Fetcher()
    total = 0
    try:
        for src in sync_sources(db):
            if total >= limit:
                break
            n = fetch_source(db, f, src, limit - total)
            log.info("%s: новых страниц %s", src.name, n)
            total += n
    finally:
        db.close()
    return total


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    log.info("всего новых страниц: %s", run(ap.parse_args().limit))


if __name__ == "__main__":
    main()
