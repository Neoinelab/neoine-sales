"""DealQuery 검증: 기본값, 페이지, 최종 업데이트 기간(양끝 포함), 텍스트 정규화·길이.

연/분기(`year`·`quarter`)의 검증은 R3(`revenue_window`)에서 본다.
"""

from dataclasses import fields
from datetime import UTC, date, datetime

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.application.ports.pagination import MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.vendor.values import SolutionId, VendorId
from tests.support.expect import raises_with
from tests.support.user_ids import uid

KEYWORD_LIMIT = 100
VENDOR = VendorId(31)
SOLUTION = SolutionId(41)


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
        "updated_from",
        "updated_to",
    ):
        assert getattr(query, condition) is None, condition


def test_sort_and_order_values_are_the_wire_values() -> None:
    assert {s.value for s in DealSort} == {
        "name",
        "revenue_amount",
        "revenue_date",
        "last_updated_at",
        "status",
        "owner",
        "customer",
        "partner",
        "vendor",
        "forecast",
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
        updated_from=date(2026, 6, 1),
        updated_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    )

    assert (query.keyword, query.owner_user_id) == ("erp", uid("park"))
    assert (query.vendor_id, query.solution_id) == (VENDOR, SOLUTION)
    assert (query.status_key, query.forecast_key) == ("introduction", "best")
    assert (query.updated_from, query.updated_to) == (date(2026, 6, 1), date(2026, 6, 30))
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


def test_an_updated_period_whose_start_is_after_its_end_is_rejected() -> None:
    with raises_with(InvalidValueError, "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"):
        DealQuery(updated_from=date(2026, 7, 1), updated_to=date(2026, 6, 30))


@pytest.mark.parametrize(
    ("updated_from", "updated_to"),
    [
        (date(2026, 6, 1), date(2026, 6, 1)),  # 같은 날(양끝 포함이므로 하루)
        (date(2026, 6, 1), None),
        (None, date(2026, 6, 30)),
        (None, None),
    ],
)
def test_valid_updated_periods_are_accepted(
    updated_from: date | None, updated_to: date | None
) -> None:
    query = DealQuery(updated_from=updated_from, updated_to=updated_to)

    assert (query.updated_from, query.updated_to) == (updated_from, updated_to)


@pytest.mark.parametrize("field", ["updated_from", "updated_to"])
def test_a_datetime_for_an_updated_date_is_rejected(field: str) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(**{field: datetime(2026, 6, 1, 9, 0, tzinfo=UTC)})  # type: ignore[arg-type]


def test_the_revenue_period_fields_no_longer_exist() -> None:
    names = {f.name for f in fields(DealQuery)}

    assert not {"revenue_from", "revenue_to"} & names
    assert {"updated_from", "updated_to"} <= names


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
