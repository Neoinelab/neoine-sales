"""PartnerMeetingQuery(AC3, P5): 검색 조건의 정규화와 검증. 모든 구현이 같은 규칙을 쓴다."""

from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.application.ports.deal_repository import SortOrder
from app.application.ports.partner_meeting_repository import (
    CONTENT_KEYWORD_MAX,
    DATE_RANGE_REVERSED,
    DEFAULT_MEETING_LIMIT,
    TEXT_FILTER_MAX,
    PartnerMeetingQuery,
    PartnerMeetingSort,
)
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with


def _kw(values: dict[str, str]) -> dict[str, Any]:
    """매개변수로 고른 검색 조건 키의 인자 묶음(mypy가 필드별 값 타입을 보지 않게)."""
    return values


def test_defaults_are_the_first_page_of_ten_by_meeting_date_descending() -> None:
    query = PartnerMeetingQuery()

    assert (query.sort, query.order) == (PartnerMeetingSort.MEETING_DATE, SortOrder.DESC)
    assert (query.offset, query.limit) == (0, DEFAULT_MEETING_LIMIT) == (0, 10)
    assert (query.partner, query.deal, query.content) == (None, None, None)
    assert (query.date_from, query.date_to, query.author_user_id) == (None, None, None)


def test_the_five_sort_columns_are_fixed() -> None:
    assert {s.value for s in PartnerMeetingSort} == {
        "meeting_date",
        "partner",
        "deal",
        "content",
        "author",
    }


def test_a_reversed_date_range_is_rejected() -> None:
    with raises_with(InvalidValueError, DATE_RANGE_REVERSED):
        PartnerMeetingQuery(date_from=date(2026, 10, 2), date_to=date(2026, 10, 1))


def test_the_reversed_range_message_is_fixed() -> None:
    assert DATE_RANGE_REVERSED == "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."


def test_a_single_day_range_and_open_ended_ranges_are_allowed() -> None:
    day = date(2026, 10, 1)

    assert PartnerMeetingQuery(date_from=day, date_to=day).date_from == day
    assert PartnerMeetingQuery(date_from=day).date_to is None
    assert PartnerMeetingQuery(date_to=day).date_from is None


@pytest.mark.parametrize("bad", [date(1899, 12, 31), date(3000, 1, 1)])
def test_a_range_date_outside_the_bounds_is_rejected(bad: date) -> None:
    with pytest.raises(InvalidValueError, match="1900-01-01"):
        PartnerMeetingQuery(date_from=bad)
    with pytest.raises(InvalidValueError, match="1900-01-01"):
        PartnerMeetingQuery(date_to=bad)


def test_a_datetime_in_the_range_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        PartnerMeetingQuery(date_from=datetime(2026, 10, 1, tzinfo=UTC))


@pytest.mark.parametrize("field", ["partner", "deal", "content"])
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_text_filters_become_none(field: str, blank: str) -> None:
    assert getattr(PartnerMeetingQuery(**_kw({field: blank})), field) is None


@pytest.mark.parametrize("field", ["partner", "deal", "content"])
def test_text_filters_are_trimmed(field: str) -> None:
    assert getattr(PartnerMeetingQuery(**_kw({field: "  한빛  "})), field) == "한빛"


def test_the_content_filter_is_limited_to_100_characters() -> None:
    assert PartnerMeetingQuery(content="a" * CONTENT_KEYWORD_MAX).content == "a" * 100
    with pytest.raises(InvalidValueError, match="100"):
        PartnerMeetingQuery(content="a" * (CONTENT_KEYWORD_MAX + 1))


@pytest.mark.parametrize("field", ["partner", "deal"])
def test_the_partner_and_deal_filters_are_limited_to_200_characters(field: str) -> None:
    assert len(getattr(PartnerMeetingQuery(**_kw({field: "a" * TEXT_FILTER_MAX})), field)) == 200
    with pytest.raises(InvalidValueError, match="200"):
        PartnerMeetingQuery(**_kw({field: "a" * (TEXT_FILTER_MAX + 1)}))


@pytest.mark.parametrize("field", ["partner", "deal", "content"])
def test_nul_in_a_text_filter_is_rejected(field: str) -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        PartnerMeetingQuery(**_kw({field: "a\x00b"}))


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
def test_page_bounds_are_checked(offset: int, limit: int) -> None:
    with pytest.raises(InvalidValueError):
        PartnerMeetingQuery(offset=offset, limit=limit)


@pytest.mark.parametrize(("offset", "limit"), [(0, 1), (0, 200), (500, 10)])
def test_valid_page_bounds_are_accepted(offset: int, limit: int) -> None:
    query = PartnerMeetingQuery(offset=offset, limit=limit)

    assert (query.offset, query.limit) == (offset, limit)
