"""Фильтры каталога (H2.1) — каждый по отдельности + available_from_region на 4 вариантах."""

from datetime import timedelta

import pytest

from app.catalog import EventFilter, search
from app.models import utcnow
from tests.conftest import add_event


def slugs(db, **kw) -> set[str]:
    items, total = search(db, EventFilter(limit=100, **kw))
    assert total == len(items)
    return {e.slug for e in items}


@pytest.fixture
def catalog(db):
    now = utcnow()
    add_event(db, slug="online", format="online", type="olympiad", goal_codes=",admission,portfolio,",
              subject_codes=",math,", grade_min=9, grade_max=11, price_kind="free", level="federal",
              entry_kind="open", title="Олимпиада Физтех", registration_deadline=now + timedelta(days=5))
    add_event(db, slug="offline-77", format="offline", region_codes=",77,", type="camp", goal_codes=",free_trip,",
              subject_codes=",informatics,", grade_min=8, grade_max=9, price_kind="paid", level="regional",
              entry_kind="selection", registration_deadline=now + timedelta(days=40))
    add_event(db, slug="offline-50", format="offline", region_codes=",50,", type="hackathon", goal_codes=",team,",
              price_kind="free", entry_kind="open", registration_deadline=None, starts_at=now + timedelta(days=3))
    add_event(db, slug="federal-trip", format="offline", is_federal=True, travel_covered="yes", type="camp",
              goal_codes=",free_trip,skills,", price_kind="quota", registration_deadline=now + timedelta(days=20))
    add_event(db, slug="past", registration_deadline=now - timedelta(days=1))
    add_event(db, slug="draft", status="draft")
    return db


def test_past_and_draft_hidden(catalog):
    assert {"past", "draft"}.isdisjoint(slugs(catalog))


def test_types(catalog):
    assert slugs(catalog, types=["camp"]) == {"offline-77", "federal-trip"}


def test_goals(catalog):
    assert slugs(catalog, goals=["free_trip"]) == {"offline-77", "federal-trip"}
    assert slugs(catalog, goals=["team", "admission"]) == {"offline-50", "online"}


def test_subjects(catalog):
    assert slugs(catalog, subjects=["math"]) == {"online"}


def test_grade_null_bounds_pass(catalog):
    assert slugs(catalog, grade=10) == {"online", "offline-50", "federal-trip"}


def test_format(catalog):
    assert slugs(catalog, format="online") == {"online"}


def test_price(catalog):
    assert slugs(catalog, price_kinds=["free"]) == {"online", "offline-50"}


def test_travel_covered(catalog):
    assert slugs(catalog, travel_covered=True) == {"federal-trip"}


def test_entry_kinds(catalog):
    assert slugs(catalog, entry_kinds=["selection"]) == {"offline-77"}


def test_levels(catalog):
    assert slugs(catalog, levels=["regional"]) == {"offline-77"}


def test_deadline_before(catalog):
    assert slugs(catalog, deadline_before=(utcnow() + timedelta(days=10)).date()) == {"online"}


def test_only_with_deadline(catalog):
    assert "offline-50" not in slugs(catalog, only_with_deadline=True)


def test_q_cyrillic_case_insensitive(catalog):
    assert slugs(catalog, q="физтех") == {"online"}


def test_available_from_region_four_variants(catalog):
    # онлайн — да; офлайн в моём (77) — да; офлайн в другом (50) — нет; федеральное с проездом — да
    assert slugs(catalog, region_code="77", available_from_region=True) == {"online", "offline-77", "federal-trip"}


def test_sort_deadline(catalog):
    items, _ = search(catalog, EventFilter(sort="deadline"))
    assert [e.slug for e in items][:3] == ["online", "federal-trip", "offline-77"]


def test_pagination(catalog):
    items, total = search(catalog, EventFilter(limit=2, offset=0))
    assert len(items) == 2 and total == 4
