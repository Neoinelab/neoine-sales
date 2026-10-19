"""DealQuery(Deal 검색 조건) 검증: 기본값, 페이지, 기간(양끝 포함), 텍스트 정규화·길이.

연/분기(`year`·`quarter`)와 BANT 조건의 검증은 R3(`revenue_window`)에서 본다.
"""

from datetime import date
from uuid import UUID

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.application.ports.pagination import MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import SolutionId, VendorId
from tests.support.expect import raises_with
from tests.support.user_ids import uid

KEYWORD_LIMIT = 100
VENDOR = VendorId(UUID(int=31))
SOLUTION = SolutionId(UUID(int=41))


def test_defaults_are_the_first_page_of_twenty_newest_first_without_conditions() -> None:
    query = DealQuery()

    assert (query.offset, query.limit) == (0, 20)
    assert (query.sort, query.order) == (DealSort.LAST_UPDATED_AT, SortOrder.DESC)
    for condition in (
        "keyword",
        "owner_user_id",
        "vendor_id",
        "solution_id",
        "status_key",
        "forecast_key",
        "year",
        "quarter",
        "revenue_from",
        "revenue_to",
    ):
        assert getattr(query, condition) is None, condition
    assert dict(query.bant_label_ids) == {}


def test_sort_and_order_values_are_the_wire_values() -> None:
    assert {s.value for s in DealSort} == {
        "name",
        "revenue_amount",
        "revenue_date",
        "last_updated_at",
        "status",
    }
    assert {o.value for o in SortOrder} == {"asc", "desc"}


def test_given_conditions_are_kept() -> None:
    query = DealQuery(
        keyword="erp",
        owner_user_id=uid("park"),
        vendor_id=VENDOR,
        solution_id=SOLUTION,
        status_key="introduction",
        forecast_key="best",
        revenue_from=date(2026, 6, 1),
        revenue_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    )

    assert (query.keyword, query.owner_user_id) == ("erp", uid("park"))
    assert (query.vendor_id, query.solution_id) == (VENDOR, SOLUTION)
    assert (query.status_key, query.forecast_key) == ("introduction", "best")
    assert (query.revenue_from, query.revenue_to) == (date(2026, 6, 1), date(2026, 6, 30))
    assert (query.offset, query.limit) == (3, 7)


def test_the_old_conditions_are_gone() -> None:
    query = DealQuery()

    for removed in ("customer_id", "partner_id", "stage", "owner"):
        assert not hasattr(query, removed), removed
    with pytest.raises(TypeError):
        DealQuery(stage="lost")  # type: ignore[call-arg]


def test_a_negative_offset_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(offset=-1)


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_a_limit_out_of_range_is_rejected(limit: int) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(limit=limit)


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_limit_boundaries_are_accepted(limit: int) -> None:
    assert DealQuery(limit=limit).limit == limit


def test_a_period_whose_start_is_after_its_end_is_rejected() -> None:
    with raises_with(InvalidValueError, "기간의 시작은 끝보다 늦을 수 없습니다"):
        DealQuery(revenue_from=date(2026, 7, 1), revenue_to=date(2026, 6, 30))


@pytest.mark.parametrize(
    ("revenue_from", "revenue_to"),
    [
        (date(2026, 6, 1), date(2026, 6, 1)),  # 같은 날(양끝 포함이므로 하루)
        (date(2026, 6, 1), None),
        (None, date(2026, 6, 30)),
        (None, None),
    ],
)
def test_valid_periods_are_accepted(revenue_from: date | None, revenue_to: date | None) -> None:
    query = DealQuery(revenue_from=revenue_from, revenue_to=revenue_to)

    assert (query.revenue_from, query.revenue_to) == (revenue_from, revenue_to)


def test_blank_keyword_becomes_none() -> None:
    assert DealQuery(keyword="   ").keyword is None


def test_keyword_is_trimmed() -> None:
    assert DealQuery(keyword=" erp ").keyword == "erp"


def test_keyword_allows_the_limit_and_rejects_one_over() -> None:
    assert DealQuery(keyword="a" * KEYWORD_LIMIT).keyword == "a" * KEYWORD_LIMIT
    with pytest.raises(InvalidValueError):
        DealQuery(keyword="a" * (KEYWORD_LIMIT + 1))


def test_a_nul_character_in_the_keyword_is_rejected() -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(keyword="a\x00b")


def test_the_old_vendor_and_solution_text_conditions_are_gone() -> None:
    query = DealQuery()

    assert not hasattr(query, "vendor")
    assert not hasattr(query, "solution")
    with pytest.raises(TypeError):
        DealQuery(vendor="SAP")  # type: ignore[call-arg]


def test_quarter_without_year_is_accepted() -> None:
    query = DealQuery(quarter=2)

    assert (query.year, query.quarter) == (None, 2)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_is_rejected_without_year(quarter: int) -> None:
    with raises_with(InvalidValueError, "분기는 1~4 중에서 선택하세요."):
        DealQuery(quarter=quarter)
