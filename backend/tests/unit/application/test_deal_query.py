"""DealQuery(Deal 검색 조건) 검증: 페이지, 기간 순서, 텍스트 정규화·길이."""

from datetime import date
from uuid import uuid4

import pytest

from app.application.ports.deal_repository import KEYWORD_MAX, DealQuery
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.customer.value_objects import CustomerId
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import OWNER_MAX, VENDOR_MAX
from app.domain.partner.value_objects import PartnerId


def test_deal_query_defaults_to_first_page_without_conditions() -> None:
    query = DealQuery()

    assert (query.offset, query.limit) == (0, DEFAULT_LIMIT)
    assert DEFAULT_LIMIT == 50
    assert query.keyword is None
    assert query.customer_id is None
    assert query.partner_id is None
    assert query.owner is None
    assert query.vendor is None
    assert query.revenue_from is None
    assert query.revenue_to is None
    assert query.stage is None


def test_deal_query_keeps_stage() -> None:
    assert DealQuery(stage=DealStage.LOST).stage is DealStage.LOST


def test_deal_query_keeps_given_conditions() -> None:
    customer_id, partner_id = CustomerId(uuid4()), PartnerId(uuid4())

    query = DealQuery(
        keyword="erp",
        customer_id=customer_id,
        partner_id=partner_id,
        owner="박영업",
        vendor="SAP",
        revenue_from=date(2026, 6, 1),
        revenue_to=date(2026, 7, 1),
        offset=3,
        limit=7,
    )

    assert query.keyword == "erp"
    assert query.customer_id == customer_id
    assert query.partner_id == partner_id
    assert (query.owner, query.vendor) == ("박영업", "SAP")
    assert (query.revenue_from, query.revenue_to) == (date(2026, 6, 1), date(2026, 7, 1))
    assert (query.offset, query.limit) == (3, 7)


def test_deal_query_rejects_negative_offset() -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(offset=-1)


@pytest.mark.parametrize("limit", [0, MAX_LIMIT + 1])
def test_deal_query_rejects_limit_out_of_range(limit: int) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(limit=limit)


@pytest.mark.parametrize("limit", [1, MAX_LIMIT])
def test_deal_query_accepts_limit_boundaries(limit: int) -> None:
    assert DealQuery(limit=limit).limit == limit


@pytest.mark.parametrize(
    ("revenue_from", "revenue_to"),
    [(date(2026, 6, 1), date(2026, 6, 1)), (date(2026, 7, 1), date(2026, 6, 1))],
    ids=["same-day", "from-after-to"],
)
def test_deal_query_rejects_revenue_from_not_before_to(
    revenue_from: date, revenue_to: date
) -> None:
    with pytest.raises(InvalidValueError):
        DealQuery(revenue_from=revenue_from, revenue_to=revenue_to)


def test_deal_query_accepts_only_one_revenue_bound() -> None:
    assert DealQuery(revenue_from=date(2026, 6, 1)).revenue_to is None
    assert DealQuery(revenue_to=date(2026, 6, 1)).revenue_from is None


def test_deal_query_treats_blank_text_conditions_as_none() -> None:
    query = DealQuery(keyword="   ", owner="  ", vendor="\t")

    assert query.keyword is None
    assert query.owner is None
    assert query.vendor is None


def test_deal_query_strips_text_conditions() -> None:
    query = DealQuery(keyword=" erp ", owner=" 박영업 ", vendor=" SAP ")

    assert (query.keyword, query.owner, query.vendor) == ("erp", "박영업", "SAP")


def test_deal_query_keeps_owner_and_vendor_case() -> None:
    query = DealQuery(owner="Park", vendor="sap")

    assert (query.owner, query.vendor) == ("Park", "sap")


def test_deal_query_rejects_keyword_over_max_length() -> None:
    assert KEYWORD_MAX == 100
    assert DealQuery(keyword="a" * KEYWORD_MAX).keyword == "a" * KEYWORD_MAX
    with pytest.raises(InvalidValueError):
        DealQuery(keyword="a" * (KEYWORD_MAX + 1))


def test_deal_query_rejects_owner_over_max_length() -> None:
    assert DealQuery(owner="a" * OWNER_MAX).owner == "a" * OWNER_MAX
    with pytest.raises(InvalidValueError):
        DealQuery(owner="a" * (OWNER_MAX + 1))


def test_deal_query_rejects_vendor_over_max_length() -> None:
    assert DealQuery(vendor="a" * VENDOR_MAX).vendor == "a" * VENDOR_MAX
    with pytest.raises(InvalidValueError):
        DealQuery(vendor="a" * (VENDOR_MAX + 1))


def test_deal_query_has_no_owner_user_condition_by_default() -> None:
    assert DealQuery().owner_user_id is None


def test_deal_query_keeps_owner_user_id() -> None:
    assert DealQuery(owner_user_id="u-1").owner_user_id == "u-1"


def test_deal_query_strips_owner_user_id_and_keeps_its_case() -> None:
    assert DealQuery(owner_user_id="  Alice@AD ").owner_user_id == "Alice@AD"


def test_deal_query_treats_blank_owner_user_id_as_none() -> None:
    assert DealQuery(owner_user_id="   ").owner_user_id is None


def test_deal_query_rejects_owner_user_id_over_max_length() -> None:
    assert DealQuery(owner_user_id="u" * 200).owner_user_id == "u" * 200
    with pytest.raises(InvalidValueError):
        DealQuery(owner_user_id="u" * 201)
