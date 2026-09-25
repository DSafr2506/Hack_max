"""Конвейер наполнения: ответ модели → проверка → кандидат → одобрение человеком. OpenRouter замокан."""

import json

import httpx
import pytest

from app import extract, fetch, llm
from app.models import Candidate, Event, RawDocument

PAGE = """Олимпиада «Тест» по математике для 9–11 классов.
Регистрация до 10 октября 2026 года. Отборочный тур 12 октября онлайн.
Участие бесплатное. Победители получают 100 баллов при поступлении в вуз-организатор.
Организатор: Университет Тест."""

GOOD = {
    "title": "Олимпиада «Тест» по математике",
    "type": "olympiad",
    "short_description": "Для 9–11 классов, отбор онлайн",
    "description": "Отборочный тур 12 октября онлайн.",
    "organizer": "Университет Тест",
    "organizer_kind": "university",
    "format": "online",
    "region_codes": [],
    "is_federal": True,
    "grade_min": 9,
    "grade_max": 11,
    "participation": "individual",
    "registration_deadline": "2026-10-10",
    "starts_at": "2026-10-12",
    "ends_at": None,
    "price_kind": "free",
    "travel_covered": "yes",  # в тексте о проезде ни слова — должно сброситься
    "accommodation_covered": "unknown",
    "entry_kind": "open",
    "registration_url": "https://test.example/reg",
    "level": "federal",
    "goals": ["admission", "portfolio"],
    "subjects": ["math"],
    "benefit_note": "Победители получают 100 баллов при поступлении в вуз-организатор.",
}


def fake_llm(responses):
    """responses — список JSON-строк, которые по очереди вернёт «OpenRouter»."""
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        content = responses[min(len(calls) - 1, len(responses) - 1)]
        return httpx.Response(
            200,
            json={
                "model": "deepseek/deepseek-v4.1-flash",
                "choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 1200, "completion_tokens": 300, "cost": 0.0004},
            },
        )

    llm.set_transport(httpx.MockTransport(handler))
    return calls


@pytest.fixture(autouse=True)
def reset_llm():
    yield
    llm.set_transport(None)


def doc(db, text=PAGE, url="https://test.example/olymp"):
    d = RawDocument(url=url, text=text, content_hash=str(hash(text + url)))
    db.add(d)
    db.commit()
    return d


def test_good_answer_becomes_new_candidate(db):
    calls = fake_llm([json.dumps(GOOD)])
    c = extract.extract_document(db, doc(db))
    assert c.status == "new"
    assert c.payload["price_kind"] == "free"  # «бесплатное» в тексте есть
    assert c.payload["travel_covered"] == "unknown"  # про проезд не написано
    assert c.payload["benefit_note"].startswith("Победители получают")  # дословная цитата сохраняется
    assert c.payload["source_url"] == "https://test.example/olymp"
    assert c.confidence == 1.0
    assert c.tokens_in == 1200 and c.cost_usd == 0.0004
    body = calls[0]
    assert body["model"] == "deepseek/deepseek-v4.1-flash" and body["response_format"] == {"type": "json_object"}
    assert db.query(Event).count() == 0  # автопубликации нет


def test_fenced_json_is_parsed():
    assert llm.parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.parse_json('Вот ответ: {"a": 2} спасибо') == {"a": 2}


def test_invalid_answer_retried_once_then_rejected(db):
    calls = fake_llm(["не json", json.dumps({**GOOD, "type": "concert"})])
    c = extract.extract_document(db, doc(db))
    assert len(calls) == 2  # один переспрос с текстом ошибки
    assert "Ответ не прошёл проверку" not in calls[0]["messages"][-1]["content"]
    assert c.status == "rejected" and "type" in c.reject_reason


def test_retry_fixes_answer(db):
    fake_llm([json.dumps({**GOOD, "goals": ["fame"]}), json.dumps(GOOD)])
    assert extract.extract_document(db, doc(db)).status == "new"


def test_invented_benefit_and_free_removed(db):
    text = "Хакатон для школьников 8–10 классов 16–18 октября 2026 в Казани. Команды по 3–5 человек."
    fake_llm([json.dumps({**GOOD, "type": "hackathon", "benefit_note": "Даёт БВИ в любой вуз"})])
    c = extract.extract_document(db, doc(db, text=text))
    p = c.payload
    assert p["benefit_note"] is None and p["price_kind"] == "unknown" and "admission" not in p["goals"]
    assert len(p["checks"]) >= 3


def test_not_an_event(db):
    fake_llm(['{"not_an_event": true}'])
    c = extract.extract_document(db, doc(db, text="Новости университета"))
    assert c.status == "rejected" and c.reject_reason == "not_an_event"


def test_duplicate_detected(db):
    from tests.conftest import add_event

    add_event(db, title=GOOD["title"], organizer=GOOD["organizer"])
    fake_llm([json.dumps(GOOD)])
    c = extract.extract_document(db, doc(db))
    assert c.status == "duplicate" and c.event_id is not None


def test_no_key_means_rejected_not_crash(db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "llm_api_key", "")
    c = extract.extract_document(db, doc(db))
    assert c.status == "rejected" and "LLM" in c.reject_reason


def test_moderation_flow_publishes_to_feed(api, db, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "admin_token", "adm")
    h = {"X-Admin-Token": "adm"}
    fake_llm([json.dumps({**GOOD, "registration_deadline": "2099-10-10", "starts_at": "2099-10-12"})])
    c = extract.extract_document(db, doc(db))
    assert api.get("/api/events").json()["total"] == 0
    lst = api.get("/api/admin/candidates?status=new", headers=h).json()
    assert [x["id"] for x in lst] == [c.id]
    detail = api.get(f"/api/admin/candidates/{c.id}", headers=h).json()
    assert "Регистрация до 10 октября" in detail["text"]
    r = api.patch(f"/api/admin/candidates/{c.id}", json={"payload": {"grade_min": 8}}, headers=h).json()
    assert r["edited_fields"] == ["grade_min"]
    r = api.post(f"/api/admin/candidates/{c.id}/approve", headers=h)
    assert r.status_code == 200, r.text
    ev = r.json()["event"]
    assert ev["trust"]["verified_at"] and ev["trust"]["source_url"] == "https://test.example/olymp"
    assert ev["grade_min"] == 8
    feed = api.get("/api/events").json()
    assert feed["total"] == 1 and feed["items"][0]["slug"] == ev["slug"]
    q = api.get("/api/admin/quality", headers=h).json()
    assert q["approved"] == 1 and q["avg_edited_fields"] == 1.0
    assert api.post(f"/api/admin/candidates/{c.id}/approve", headers=h).status_code == 409
    assert api.get("/admin").status_code == 200


def test_html_to_text_and_links():
    html = """<html><head><title>Смена</title><script>var x=1</script></head>
    <body><nav>меню</nav><h1>Программа</h1><p>Заявки до&nbsp;1 октября</p>
    <a href="/obuchenie/nauka/smena2498">Январь</a><a href="#top">вверх</a></body></html>"""
    text, links, title = fetch.html_to_text(html, "https://sochisirius.ru/obuchenie/nauka")
    assert "Заявки до 1 октября" in text and "var x" not in text and "меню" not in text
    assert links == ["https://sochisirius.ru/obuchenie/nauka/smena2498"] and title == "Смена"


def test_save_document_dedup(db):
    assert fetch.save_document(db, None, "https://a.ru", "текст") is not None
    assert fetch.save_document(db, None, "https://b.ru", "текст") is None
    assert db.query(Candidate).count() == 0
