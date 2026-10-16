"""DealQuery(Deal 검색 조건) 검증: 기본값, 페이지, 기간(양끝 포함), 텍스트 정규화·길이.

연/분기(`year`·`quarter`)와 BANT 조건의 검증은 R3(`revenue_window`)에서 본다.
"""

from datetime import date
from typing import Any, cast

import pytest

from app.application.ports.deal_repository import DealQuery, DealSort, SortOrder
from app.application.ports.pagination import MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with
from tests.support.user_ids import uid

KEYWORD_LIMIT = 100
VENDOR_LIMIT = 100
SOLUTION_LIMIT = 200


def test_defaults_are_the_first_page_of_twenty_newest_first_without_conditions() -> None:
    query = DealQuery()

    assert (query.offset, query.limit) == (0, 20)
    assert (query.sort, query.order) == (DealSort.LAST_UPDATED_AT, SortOrder.DESC)
    for condition in (
        "keyword",
        "owner_user_id",
        "vendor",
        "solution",
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
        vendor="SAP",
        solution="S/4HANA",
        status_key="introduction",
        forecast_key="best",
        revenue_from=date(2026, 6, 1),
        revenue_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    )

    assert (query.keyword, query.owner_user_id) == ("erp", uid("park"))
    assert (query.vendor, query.solution) == ("SAP", "S/4HANA")
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


def test_blank_text_conditions_become_none() -> None:
    query = DealQuery(keyword="   ", vendor="\t", solution=" ")

    assert (query.keyword, query.vendor, query.solution) == (None, None, None)


def test_text_conditions_are_trimmed_and_vendor_keeps_its_case() -> None:
    query = DealQuery(keyword=" erp ", vendor=" sap ", solution=" S/4 ")

    assert (query.keyword, query.vendor, query.solution) == ("erp", "sap", "S/4")


@pytest.mark.parametrize(
    ("field", "limit"),
    [("keyword", KEYWORD_LIMIT), ("vendor", VENDOR_LIMIT), ("solution", SOLUTION_LIMIT)],
)
def test_text_conditions_allow_the_limit_and_reject_one_over(field: str, limit: int) -> None:
    ok: dict[str, Any] = {field: "a" * limit}
    over: dict[str, Any] = {field: "a" * (limit + 1)}
    assert getattr(DealQuery(**ok), field) == "a" * limit
    with pytest.raises(InvalidValueError):
        DealQuery(**over)


@pytest.mark.parametrize("field", ["keyword", "vendor", "solution"])
def test_a_nul_character_in_a_text_condition_is_rejected(field: str) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(**cast("dict[str, Any]", {field: "a\x00b"}))
