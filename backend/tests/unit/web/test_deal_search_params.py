"""웹 쿼리 모델(R2): 목록 검색 파라미터가 DealQuery로 바뀌는 방식과 검증 (AC-22·22a·22e).

mine=true는 요청자가 Owner인 딜이고 owner_user_id보다 우선한다. 연/분기·BANT·정렬 파라미터는 R3다.
Vendor·Solution 조건은 id(UUID)다.
"""

import importlib
from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.application.ports.deal_repository import DealSort, SortOrder
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")
VENDOR = uuid4()


def test_defaults_are_the_first_page_of_twenty_newest_first_without_conditions() -> None:
    query = DealSearchParams().to_query(VIEWER)

    assert (query.offset, query.limit) == (0, 20)
    assert (query.sort, query.order) == (DealSort.LAST_UPDATED_AT, SortOrder.DESC)
    assert query.owner_user_id is None
    assert query.keyword is None


def test_every_basic_condition_reaches_the_query() -> None:
    owner = uid("park")

    query = DealSearchParams(
        keyword="erp",
        owner_user_id=owner,
        vendor_id=VENDOR,
        status_key="introduction",
        revenue_from=date(2026, 6, 1),
        revenue_to=date(2026, 6, 30),
        offset=3,
        limit=7,
    ).to_query(VIEWER)

    assert (query.keyword, query.owner_user_id, query.vendor_id) == ("erp", owner, VENDOR)
    assert query.status_key == "introduction"
    assert (query.revenue_from, query.revenue_to) == (date(2026, 6, 1), date(2026, 6, 30))
    assert (query.offset, query.limit) == (3, 7)


def test_mine_maps_to_the_viewers_user_id_as_the_owner_condition() -> None:
    assert DealSearchParams(mine=True).to_query(VIEWER).owner_user_id == VIEWER


def test_without_mine_or_with_mine_false_there_is_no_owner_condition() -> None:
    assert DealSearchParams().to_query(VIEWER).owner_user_id is None
    assert DealSearchParams(mine=False).to_query(VIEWER).owner_user_id is None


def test_mine_wins_over_an_explicit_owner() -> None:
    query = DealSearchParams(mine=True, owner_user_id=uid("someone")).to_query(VIEWER)

    assert query.owner_user_id == VIEWER


def test_owner_user_id_does_not_need_mine() -> None:
    target = uid("someone")

    query = DealSearchParams(owner_user_id=target).to_query(VIEWER)

    assert query.owner_user_id == target


def test_mine_keeps_the_other_conditions() -> None:
    query = DealSearchParams(mine=True, keyword="erp", offset=3, limit=7).to_query(VIEWER)

    assert (query.keyword, query.offset, query.limit, query.owner_user_id) == (
        "erp",
        3,
        7,
        VIEWER,
    )


@pytest.mark.parametrize("limit", [1, 200])
def test_limit_boundaries_are_accepted(limit: int) -> None:
    assert DealSearchParams(limit=limit).limit == limit


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"offset": -1}])
def test_page_values_out_of_range_are_rejected(params: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize(
    "params",
    [
        {"mine": "maybe"},
        {"owner_user_id": "u-2"},
        {"revenue_from": "2026/06/01"},
        {"keyword": "a" * 101},
        {"vendor_id": "SAP"},  # 이름이 아니라 UUID여야 한다
        {"status_key": "a" * 51},
    ],
)
def test_malformed_values_are_rejected(params: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize(
    "params",
    [
        {"owner": "박영업"},  # 이름 문자열 조건은 없다
        {"vendor": "SAP"},  # 이름 조건은 id 조건(vendor_id)으로 바뀌었다
        {"solution": "S/4HANA"},
        {"stage": "lost"},
        {"customer_id": str(uuid4())},
        {"partner_id": str(uuid4())},
        {"unknown": "x"},
    ],
)
def test_unknown_or_retired_parameters_are_rejected(params: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


def test_the_pipeline_params_model_is_gone() -> None:
    with pytest.raises(ImportError):
        importlib.import_module("app.web.schemas.deal_stage")


def test_vendor_id_and_solution_id_are_uuids() -> None:
    vendor, solution = uuid4(), uuid4()

    query = DealSearchParams(vendor_id=vendor, solution_id=solution).to_query(VIEWER)

    assert (query.vendor_id, query.solution_id) == (vendor, solution)


def test_vendor_conditions_default_to_none() -> None:
    query = DealSearchParams().to_query(VIEWER)

    assert (query.vendor_id, query.solution_id) == (None, None)
