"""PartnerMeetingQuery: 검색 조건의 정규화와 검증. 모든 구현이 같은 규칙을 쓴다."""

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
    """조건이 없으면 첫 10건을 미팅 날짜 내림차순으로 읽는다.

    테스트 코드: PA-013
    """
    # when: 조건 없이 질의를 만든다
    query = PartnerMeetingQuery()
    # then: 미팅 날짜 내림차순, offset 0, limit 10이고 조건은 모두 비었다
    assert (query.sort, query.order) == (PartnerMeetingSort.MEETING_DATE, SortOrder.DESC)
    assert (query.offset, query.limit) == (0, DEFAULT_MEETING_LIMIT) == (0, 10)
    assert (query.partner, query.content) == (None, None)
    assert (query.date_from, query.date_to, query.author_user_id) == (None, None, None)


def test_the_four_sort_columns_are_fixed() -> None:
    """정렬 열은 네 개로 고정이다."""
    # when·then: 정렬 열 값을 모으면 네 열뿐이다
    assert {s.value for s in PartnerMeetingSort} == {
        "meeting_date",
        "partner",
        "content",
        "author",
    }


def test_a_reversed_date_range_is_rejected() -> None:
    """시작이 끝보다 늦은 날짜 범위는 거절된다.

    테스트 코드: PA-028
    """
    # when·then: 10-02 ~ 10-01 범위는 안내 문구와 함께 거절된다
    with raises_with(InvalidValueError, DATE_RANGE_REVERSED):
        PartnerMeetingQuery(date_from=date(2026, 10, 2), date_to=date(2026, 10, 1))


def test_the_reversed_range_message_is_fixed() -> None:
    """역전 범위 안내 문구는 고정이다."""
    # when·then: 상수 문구를 읽으면 명세와 같다
    assert DATE_RANGE_REVERSED == "미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다."


def test_a_single_day_range_and_open_ended_ranges_are_allowed() -> None:
    """하루짜리 범위와 한쪽만 준 범위는 허용된다.

    테스트 코드: PA-024
    """
    # given: 하루
    day = date(2026, 10, 1)
    # when: 같은 날을 양끝으로, 시작만, 끝만 줘서 질의를 만든다
    both = PartnerMeetingQuery(date_from=day, date_to=day)
    only_from = PartnerMeetingQuery(date_from=day)
    only_to = PartnerMeetingQuery(date_to=day)
    # then: 모두 만들어지고 비운 쪽은 None이다
    assert both.date_from == day
    assert only_from.date_to is None
    assert only_to.date_from is None


@pytest.mark.parametrize("bad", [date(1899, 12, 31), date(3000, 1, 1)])
def test_a_range_date_outside_the_bounds_is_rejected(bad: date) -> None:
    """범위 밖 검색 날짜는 시작·끝 어느 쪽이든 거절된다.

    테스트 코드: PA-028
    """
    # when·then: 시작에 범위 밖 날짜를 주면 범위 문구로 거절된다
    with pytest.raises(InvalidValueError, match="1900-01-01"):
        PartnerMeetingQuery(date_from=bad)
    # when·then: 끝에 범위 밖 날짜를 줘도 거절된다
    with pytest.raises(InvalidValueError, match="1900-01-01"):
        PartnerMeetingQuery(date_to=bad)


def test_a_datetime_in_the_range_is_rejected() -> None:
    """시각이 든 값은 날짜 조건으로 받지 않는다."""
    # when·then: datetime을 주면 거절된다
    with pytest.raises(InvalidValueError):
        PartnerMeetingQuery(date_from=datetime(2026, 10, 1, tzinfo=UTC))


@pytest.mark.parametrize("field", ["partner", "content"])
@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_blank_text_filters_become_none(field: str, blank: str) -> None:
    """공백뿐인 텍스트 조건은 무시된다.

    테스트 코드: PA-027
    """
    # when: 공백뿐인 텍스트 조건으로 질의를 만든다
    query = PartnerMeetingQuery(**_kw({field: blank}))
    # then: 조건이 None이다
    assert getattr(query, field) is None


@pytest.mark.parametrize("field", ["partner", "content"])
def test_text_filters_are_trimmed(field: str) -> None:
    """텍스트 조건의 앞뒤 공백은 지워진다.

    테스트 코드: PA-027
    """
    # when: 앞뒤에 공백이 붙은 조건으로 질의를 만든다
    query = PartnerMeetingQuery(**_kw({field: "  한빛  "}))
    # then: 공백이 지워진다
    assert getattr(query, field) == "한빛"


def test_the_content_filter_is_limited_to_100_characters() -> None:
    """내용 조건은 100자까지다.

    테스트 코드: PA-029
    """
    # when: 100자로 질의를 만든다
    query = PartnerMeetingQuery(content="a" * CONTENT_KEYWORD_MAX)
    # then: 받아들여진다
    assert query.content == "a" * 100
    # when·then: 101자는 거절된다
    with pytest.raises(InvalidValueError, match="100"):
        PartnerMeetingQuery(content="a" * (CONTENT_KEYWORD_MAX + 1))


def test_the_partner_filter_is_limited_to_200_characters() -> None:
    """파트너 조건은 200자까지다.

    테스트 코드: PA-029
    """
    # when: 200자로 질의를 만든다
    query = PartnerMeetingQuery(partner="a" * TEXT_FILTER_MAX)
    # then: 받아들여진다
    assert len(query.partner or "") == 200
    # when·then: 201자는 거절된다
    with pytest.raises(InvalidValueError, match="200"):
        PartnerMeetingQuery(partner="a" * (TEXT_FILTER_MAX + 1))


def test_query_has_no_deal_condition() -> None:
    """질의에는 Deal 조건이 없다.

    테스트 코드: PA-029
    """
    # when·then: deal 인자를 주면 TypeError다
    with pytest.raises(TypeError):
        PartnerMeetingQuery(**_kw({"deal": "ERP"}))


@pytest.mark.parametrize("field", ["partner", "content"])
def test_nul_in_a_text_filter_is_rejected(field: str) -> None:
    """텍스트 조건의 NUL은 거절된다."""
    # when·then: NUL이 든 조건은 거절된다
    with pytest.raises(InvalidValueError, match="NUL"):
        PartnerMeetingQuery(**_kw({field: "a\x00b"}))


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
def test_page_bounds_are_checked(offset: int, limit: int) -> None:
    """offset 0 미만과 limit 1 미만·200 초과는 거절된다.

    테스트 코드: PA-019
    """
    # when·then: 범위 밖 쪽 값은 거절된다
    with pytest.raises(InvalidValueError):
        PartnerMeetingQuery(offset=offset, limit=limit)


@pytest.mark.parametrize(("offset", "limit"), [(0, 1), (0, 200), (500, 10)])
def test_valid_page_bounds_are_accepted(offset: int, limit: int) -> None:
    """limit 200까지와 큰 offset은 받아들여진다.

    테스트 코드: PA-019
    """
    # when: 경계 안의 쪽 값으로 질의를 만든다
    query = PartnerMeetingQuery(offset=offset, limit=limit)
    # then: 값이 그대로다
    assert (query.offset, query.limit) == (offset, limit)
