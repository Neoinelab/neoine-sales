"""ContactQuery 검증(AC-17): 구분 필터, 키워드 정규화·길이, 페이지 규칙.

구 CustomerQuery/PartnerQuery 테스트(키워드 100자, 공백 정리, 페이지 경계)를 그대로 옮겼다.
"""

import pytest
from app.application.ports.contact_repository import KEYWORD_MAX, ContactQuery
from app.domain.contact.values import ContactKind

from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.common.errors import InvalidValueError


def test_keyword_max_is_100() -> None:
    assert KEYWORD_MAX == 100


def test_query_defaults_to_all_kinds_first_page_without_keyword() -> None:
    query = ContactQuery()

    assert query.kind is None
    assert query.keyword is None
    assert (query.offset, query.limit) == (0, DEFAULT_LIMIT)


def test_query_keeps_given_values() -> None:
    query = ContactQuery(kind=ContactKind.PARTNER, keyword="네오인", offset=3, limit=7)

    assert (query.kind, query.keyword, query.offset, query.limit) == (
        ContactKind.PARTNER,
        "네오인",
        3,
        7,
    )


def test_query_strips_keyword_and_blank_is_none() -> None:
    assert ContactQuery(keyword="  erp  ").keyword == "erp"
    assert ContactQuery(keyword="   ").keyword is None
    assert ContactQuery(keyword="\t").keyword is None


def test_query_rejects_keyword_over_100_chars() -> None:
    assert ContactQuery(keyword="a" * 100).keyword == "a" * 100
    with pytest.raises(InvalidValueError):
        ContactQuery(keyword="a" * 101)


def test_query_rejects_nul_in_keyword() -> None:
    with pytest.raises(InvalidValueError):
        ContactQuery(keyword="a\x00b")


def test_query_rejects_negative_offset() -> None:
    with pytest.raises(InvalidValueError):
        ContactQuery(offset=-1)


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_query_rejects_limit_out_of_range(limit: int) -> None:
    with pytest.raises(InvalidValueError):
        ContactQuery(limit=limit)


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_query_accepts_limit_boundaries(limit: int) -> None:
    assert ContactQuery(limit=limit).limit == limit
