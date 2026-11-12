"""ContactQuery 검증: 구분 필터, 키워드 정규화·길이, 페이지 규칙.

구 CustomerQuery/PartnerQuery 테스트(키워드 100자, 공백 정리, 페이지 경계)를 그대로 옮겼다.
"""

import pytest

from app.application.ports.contact_repository import KEYWORD_MAX, ContactQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.contact.values import ContactKind


def test_keyword_max_is_100() -> None:
    """검색어 최대 길이는 100자다.

    테스트 코드: CT-035
    """
    # when·then: 상수 KEYWORD_MAX를 읽는다 → 100이다
    assert KEYWORD_MAX == 100


def test_query_defaults_to_all_kinds_first_page_without_keyword() -> None:
    """조건 없이 만든 조회는 모든 종류의 첫 페이지이고 키워드가 없다.

    테스트 코드: CT-025
    """
    # when: 기본 조건을 만든다
    query = ContactQuery()

    # then: 종류·키워드 없음, offset 0, 기본 limit이다
    assert query.kind is None
    assert query.keyword is None
    assert (query.offset, query.limit) == (0, DEFAULT_LIMIT)


def test_query_keeps_given_values() -> None:
    """준 종류·키워드·offset·limit을 그대로 가진다.

    테스트 코드: CT-024
    """
    # when: 모든 조건을 주고 만든다
    query = ContactQuery(kind=ContactKind.PARTNER, keyword="네오인", offset=3, limit=7)

    # then: 준 값 그대로다
    assert (query.kind, query.keyword, query.offset, query.limit) == (
        ContactKind.PARTNER,
        "네오인",
        3,
        7,
    )


def test_query_strips_keyword_and_blank_is_none() -> None:
    """키워드는 앞뒤 공백을 지우고 공백뿐이면 조건 없음(None)이다.

    테스트 코드: CT-030
    """
    # when: 공백이 붙은 키워드와 공백뿐인 키워드로 만든다
    keyword = ContactQuery(keyword="  erp  ").keyword
    # then: 앞뒤 공백이 지워지고 공백뿐이면 None이다
    assert keyword == "erp"
    assert ContactQuery(keyword="   ").keyword is None
    assert ContactQuery(keyword="\t").keyword is None


def test_query_rejects_keyword_over_100_chars() -> None:
    """키워드 100자는 받고 101자는 거절한다.

    테스트 코드: CT-035
    """
    assert ContactQuery(keyword="a" * 100).keyword == "a" * 100
    # when·then: 100자와 101자 키워드로 만든다 → 100자는 되고 101자는 입력값 오류다
    with pytest.raises(InvalidValueError):
        ContactQuery(keyword="a" * 101)


def test_query_rejects_nul_in_keyword() -> None:
    """키워드에 NUL이 있으면 입력값 오류다.

    테스트 코드: CT-036
    """
    # when·then: NUL이 든 키워드로 만든다 → 입력값 오류다
    with pytest.raises(InvalidValueError):
        ContactQuery(keyword="a\x00b")


def test_query_rejects_negative_offset() -> None:
    """음수 offset은 거절한다.

    테스트 코드: CT-038
    """
    # when·then: offset -1로 만든다 → 입력값 오류다
    with pytest.raises(InvalidValueError):
        ContactQuery(offset=-1)


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_query_rejects_limit_out_of_range(limit: int) -> None:
    """limit 0과 최대값 초과는 거절한다.

    테스트 코드: CT-038
    """
    # when·then: 범위 밖 limit으로 만든다 → 입력값 오류다
    with pytest.raises(InvalidValueError):
        ContactQuery(limit=limit)


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_query_accepts_limit_boundaries(limit: int) -> None:
    """limit 1과 최대값은 받는다.

    테스트 코드: CT-038
    """
    # when: 경계 limit으로 만든다
    actual = ContactQuery(limit=limit).limit
    # then: 그대로 가진다
    assert actual == limit
