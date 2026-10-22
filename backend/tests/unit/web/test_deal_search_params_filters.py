"""웹 쿼리 모델의 확장 필터·정렬(R3, AC-22a~22d): forecast, 연/분기, sort/order, 위험 필터.

`DealSearchParams.to_query(viewer)`가 `DealQuery`를 만든다. sort·order는 화이트리스트 밖이면 422,
quarter는 연도 없이도 쓸 수 있다(올해 채우기는 ListDeals가 한다). 모르는 파라미터는 여전히 거절한다.
"""

import pytest
from pydantic import ValidationError

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealSort, SortOrder
from app.domain.common.errors import InvalidValueError
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


def test_forecast_year_and_quarter_reach_the_query() -> None:
    query = DealSearchParams(forecast_key="commit", year=2026, quarter=2).to_query(VIEWER)

    assert query.forecast_key == "commit"
    assert (query.year, query.quarter) == (2026, 2)


def test_the_new_conditions_default_to_none() -> None:
    query = DealSearchParams().to_query(VIEWER)

    assert (query.forecast_key, query.year, query.quarter) == (None,) * 3
    assert (query.overdue, query.stale) == (False, False)


@pytest.mark.parametrize("sort", list(DealSort))
@pytest.mark.parametrize("order", list(SortOrder))
def test_every_whitelisted_sort_and_order_reaches_the_query(
    sort: DealSort, order: SortOrder
) -> None:
    query = DealSearchParams(sort=sort.value, order=order.value).to_query(VIEWER)

    assert (query.sort, query.order) == (sort, order)


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "revenueAmount"},  # 프런트 이름이 아니라 서버 이름만 받는다
        {"sort": "stage"},
        {"sort": "name; drop table deals"},
        {"sort": ""},
        {"order": "up"},
        {"order": "DESC"},
    ],
)
def test_a_sort_or_order_outside_the_whitelist_is_rejected(params: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize("params", [{"year": 1899}, {"year": 10000}, {"year": 2026, "quarter": 0}])
def test_a_year_or_quarter_out_of_range_is_rejected(params: dict[str, int]) -> None:
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(**params).to_query(VIEWER).revenue_window()


def test_a_quarter_above_four_is_rejected() -> None:
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(year=2026, quarter=5).to_query(VIEWER).revenue_window()


def test_quarter_without_year_reaches_the_query() -> None:
    query = DealSearchParams(quarter=2).to_query(VIEWER)

    assert (query.year, query.quarter) == (None, 2)


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_is_rejected(quarter: int) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(quarter=quarter)


@pytest.mark.parametrize("year", [1900, 9999])
def test_the_year_boundaries_are_accepted(year: int) -> None:
    assert DealSearchParams(year=year).to_query(VIEWER).year == year


@pytest.mark.parametrize(
    "params",
    [
        {"solution_id": "7"},  # 구 id 조건은 폐지됐다
        {"solution": "a" * 201},
        {"forecast_key": "a" * 51},
        {"year": "twenty"},
        {"quarter": "q2"},
    ],
)
def test_malformed_new_values_are_rejected(params: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


RETIRED_BANT_PARAMS = ["bant_budget", "bant_authority", "bant_need", "bant_timeline"]


@pytest.mark.parametrize("field", RETIRED_BANT_PARAMS)
def test_retired_bant_parameters_are_rejected(field: str) -> None:
    """BANT 목록 필터 폐지(2026-10-22): 모르는 파라미터처럼 거절한다(조용히 무시 안 함)."""
    with pytest.raises(ValidationError):
        DealSearchParams.model_validate({field: "5"})


def test_overdue_and_stale_default_to_false_and_reach_the_query() -> None:
    query = DealSearchParams().to_query(VIEWER)

    assert (query.overdue, query.stale) == (False, False)
    assert query.wants_risk() is False


@pytest.mark.parametrize("raw", ["true", "1", True])
def test_overdue_and_stale_true_reach_the_query(raw: object) -> None:
    overdue = DealSearchParams.model_validate({"overdue": raw}).to_query(VIEWER)
    stale = DealSearchParams.model_validate({"stale": raw}).to_query(VIEWER)
    both = DealSearchParams.model_validate({"overdue": raw, "stale": raw}).to_query(VIEWER)

    assert (overdue.overdue, overdue.stale) == (True, False)
    assert (stale.overdue, stale.stale) == (False, True)
    assert (both.overdue, both.stale) == (True, True)


@pytest.mark.parametrize("raw", ["false", "0"])
def test_overdue_and_stale_false_values_are_no_condition(raw: str) -> None:
    query = DealSearchParams.model_validate({"overdue": raw, "stale": raw}).to_query(VIEWER)

    assert query.wants_risk() is False


@pytest.mark.parametrize("field", ["overdue", "stale"])
@pytest.mark.parametrize("raw", ["abc", "yes please", "2"])
def test_a_non_boolean_overdue_or_stale_is_rejected(field: str, raw: str) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams.model_validate({field: raw})


def test_the_risk_filters_combine_with_mine_and_sort() -> None:
    query = DealSearchParams(mine=True, stale=True, sort="owner", order="desc").to_query(VIEWER)

    assert query.owner_user_id == VIEWER
    assert query.stale is True
    assert (query.sort, query.order) == (DealSort.OWNER, SortOrder.DESC)


def test_the_new_conditions_keep_working_together_with_mine() -> None:
    query = DealSearchParams(mine=True, year=2026, quarter=3, sort="name", order="asc").to_query(
        VIEWER
    )

    assert query.owner_user_id == VIEWER
    assert (query.year, query.quarter) == (2026, 3)
    assert (query.sort, query.order) == (DealSort.NAME, SortOrder.ASC)


@pytest.mark.parametrize("params", [{"bant_label": "x"}, {"sortBy": "name"}, {"direction": "asc"}])
def test_unknown_parameters_are_still_rejected(params: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize("value", ["open", "done", "not_done", "closed"])
def test_deal_search_params_passes_next_action_status(value: str) -> None:
    query = DealSearchParams(next_action_status=value).to_query(VIEWER)

    assert query.next_action_status == NextActionStatusFilter(value)


def test_next_action_status_defaults_to_no_condition() -> None:
    assert DealSearchParams().to_query(VIEWER).next_action_status is None


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
def test_a_next_action_status_outside_the_whitelist_is_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(next_action_status=value)
