"""CustomerQuery / PartnerQuery 검증(C-1·C-2): 키워드 정규화·길이, 페이지 규칙(고객·파트너 공통)."""

import pytest

from app.application.ports.customer_repository import KEYWORD_MAX as CUSTOMER_KEYWORD_MAX
from app.application.ports.customer_repository import CustomerQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.application.ports.partner_repository import KEYWORD_MAX as PARTNER_KEYWORD_MAX
from app.application.ports.partner_repository import PartnerQuery
from app.domain.common.errors import InvalidValueError

QUERY_TYPES = [CustomerQuery, PartnerQuery]


def test_keyword_max_is_100_for_both() -> None:
    assert CUSTOMER_KEYWORD_MAX == 100
    assert PARTNER_KEYWORD_MAX == 100


@pytest.mark.parametrize("query_type", QUERY_TYPES)
def test_query_defaults_to_first_page_without_keyword(query_type: type) -> None:
    query = query_type()

    assert query.keyword is None
    assert (query.offset, query.limit) == (0, DEFAULT_LIMIT)


@pytest.mark.parametrize("query_type", QUERY_TYPES)
def test_query_keeps_given_values(query_type: type) -> None:
    query = query_type(keyword="네오인", offset=3, limit=7)

    assert (query.keyword, query.offset, query.limit) == ("네오인", 3, 7)


@pytest.mark.parametrize("query_type", QUERY_TYPES)
def test_query_strips_keyword_and_blank_is_none(query_type: type) -> None:
    assert query_type(keyword="  erp  ").keyword == "erp"
    assert query_type(keyword="   ").keyword is None
    assert query_type(keyword="\t").keyword is None


@pytest.mark.parametrize("query_type", QUERY_TYPES)
def test_query_rejects_keyword_over_100_chars(query_type: type) -> None:
    assert query_type(keyword="a" * 100).keyword == "a" * 100
    with pytest.raises(InvalidValueError):
        query_type(keyword="a" * 101)


@pytest.mark.parametrize("query_type", QUERY_TYPES)
def test_query_rejects_negative_offset(query_type: type) -> None:
    with pytest.raises(InvalidValueError):
        query_type(offset=-1)


@pytest.mark.parametrize("query_type", QUERY_TYPES)
@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_query_rejects_limit_out_of_range(query_type: type, limit: int) -> None:
    with pytest.raises(InvalidValueError):
        query_type(limit=limit)


@pytest.mark.parametrize("query_type", QUERY_TYPES)
@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_query_accepts_limit_boundaries(query_type: type, limit: int) -> None:
    assert query_type(limit=limit).limit == limit
