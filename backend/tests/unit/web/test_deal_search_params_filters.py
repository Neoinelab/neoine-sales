"""웹 쿼리 모델의 확장 필터·정렬: forecast, 연/분기, sort/order, 위험 필터.

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
    """Forecast·연도·분기 조건이 조회 조건에 전달된다."""
    # when: 세 조건을 담은 파라미터를 조회 조건으로 바꾼다
    query = DealSearchParams(forecast_key=["commit"], year=2026, quarter=[2]).to_query(VIEWER)

    # then: 각 조건이 조회 조건에 담긴다
    assert query.forecast_keys == frozenset({"commit"})
    assert (query.year, query.quarters) == (2026, frozenset({2}))


def test_several_forecast_keys_reach_the_query() -> None:
    """여러 Forecast 키가 모두 조회 조건에 전달된다."""
    # when: Forecast 키 둘을 조회 조건으로 바꾼다
    query = DealSearchParams(forecast_key=["pipeline", "best"]).to_query(VIEWER)

    # then: 두 키가 집합에 담긴다
    assert query.forecast_keys == frozenset({"pipeline", "best"})


def test_duplicate_forecast_keys_are_one_key() -> None:
    """중복된 Forecast 키는 하나로 합쳐진다."""
    # when: 같은 키를 두 번 담아 조회 조건으로 바꾼다
    query = DealSearchParams(forecast_key=["a", "a"]).to_query(VIEWER)

    # then: 키는 하나다
    assert query.forecast_keys == frozenset({"a"})


def test_an_empty_forecast_key_list_means_no_condition() -> None:
    """빈 Forecast 키 목록은 조건 없음이다."""
    # when: 빈 목록을 조회 조건으로 바꾼다
    forecast_keys = DealSearchParams(forecast_key=[]).to_query(VIEWER).forecast_keys

    # then: 조건이 없다
    assert forecast_keys is None


def test_a_comma_inside_a_forecast_key_is_part_of_that_one_key() -> None:
    """Forecast 키 안의 쉼표는 그 키의 일부다."""
    # when: 쉼표가 든 키를 조회 조건으로 바꾼다
    query = DealSearchParams(forecast_key=["a,b"]).to_query(VIEWER)

    # then: 쪼개지지 않고 한 키다
    assert query.forecast_keys == frozenset({"a,b"})


def test_an_empty_string_forecast_key_is_accepted_as_an_unknown_key() -> None:
    """빈 문자열 Forecast 키는 알 수 없는 키로 받아들인다."""
    # when: 빈 문자열 키를 조회 조건으로 바꾼다
    query = DealSearchParams(forecast_key=[""]).to_query(VIEWER)

    # then: 빈 문자열 키가 담긴다
    assert query.forecast_keys == frozenset({""})


def test_fifty_character_keys_and_one_hundred_keys_are_accepted() -> None:
    """50자 키와 100개 키는 허용한다."""
    # when: 50자 키 하나와 키 100개를 각각 조회 조건으로 바꾼다
    long_key = DealSearchParams(forecast_key=["a" * 50]).to_query(VIEWER)
    many = DealSearchParams(forecast_key=[f"k{i}" for i in range(100)]).to_query(VIEWER)

    # then: 모두 그대로 담긴다
    assert long_key.forecast_keys == frozenset({"a" * 50})
    assert many.forecast_keys is not None
    assert len(many.forecast_keys) == 100


@pytest.mark.parametrize(
    "keys",
    [["a" * 51], ["ok", "a" * 51], [f"k{i}" for i in range(101)]],
)
def test_too_long_a_key_or_too_many_forecast_keys_are_rejected(keys: list[str]) -> None:
    """51자 키나 101개 키는 거부한다."""
    # when·then: 상한을 넘기면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(forecast_key=keys)


def test_the_new_conditions_default_to_none() -> None:
    """새 조건은 기본값이 없음(None·False)이다."""
    # when: 파라미터 없이 조회 조건으로 바꾼다
    query = DealSearchParams().to_query(VIEWER)

    # then: Forecast·연도·분기는 None이고 위험 필터는 꺼져 있다
    assert (query.forecast_keys, query.year, query.quarters) == (None,) * 3
    assert (query.overdue, query.stale) == (False, False)


@pytest.mark.parametrize("sort", list(DealSort))
@pytest.mark.parametrize("order", list(SortOrder))
def test_every_whitelisted_sort_and_order_reaches_the_query(
    sort: DealSort, order: SortOrder
) -> None:
    """허용 목록의 모든 정렬 키와 방향이 조회 조건에 전달된다."""
    # when: 정렬 키와 방향을 조회 조건으로 바꾼다
    query = DealSearchParams(sort=sort.value, order=order.value).to_query(VIEWER)

    # then: 같은 정렬 키와 방향이다
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
    """허용 목록 밖의 정렬 키나 방향은 거부한다."""
    # when·then: 허용되지 않는 값이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize(
    "params", [{"year": 1899}, {"year": 10000}, {"year": 2026, "quarter": [0]}]
)
def test_a_year_or_quarter_out_of_range_is_rejected(params: dict[str, int]) -> None:
    """범위 밖의 연도나 분기는 거부한다."""
    # when·then: 범위 밖 값이면 검증 오류나 값 오류가 난다
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(**params).to_query(VIEWER).revenue_window()


def test_a_quarter_above_four_is_rejected() -> None:
    """4를 넘는 분기는 거부한다."""
    # when·then: 5분기로 조회 기간을 구하면 오류가 난다
    with pytest.raises((ValidationError, InvalidValueError)):
        DealSearchParams(year=2026, quarter=[5]).to_query(VIEWER).revenue_window()


def test_quarter_without_year_reaches_the_query() -> None:
    """연도 없이 준 분기도 조회 조건에 전달된다."""
    # when: 분기만 담아 조회 조건으로 바꾼다
    query = DealSearchParams(quarter=[2]).to_query(VIEWER)

    # then: 연도는 없고 분기만 담긴다
    assert (query.year, query.quarters) == (None, frozenset({2}))


@pytest.mark.parametrize("quarter", [0, 5])
def test_quarter_out_of_range_is_rejected(quarter: int) -> None:
    """범위(1~4) 밖의 분기는 거부한다."""
    # when·then: 0이나 5를 주면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(quarter=[quarter])


@pytest.mark.parametrize("year", [1900, 9999])
def test_the_year_boundaries_are_accepted(year: int) -> None:
    """연도 경계값 1900·9999는 허용한다."""
    # when: 경계 연도를 조회 조건으로 바꾼다
    query = DealSearchParams(year=year).to_query(VIEWER)

    # then: 연도가 그대로다
    assert query.year == year


@pytest.mark.parametrize(
    "params",
    [
        {"solution_id": "7"},  # 구 id 조건은 폐지됐다
        {"product": "a" * 201},
        {"forecast_key": ["a" * 51]},
        {"forecast_key": [f"k{i}" for i in range(101)]},
        {"year": "twenty"},
        {"quarter": "q2"},
    ],
)
def test_malformed_new_values_are_rejected(params: dict[str, object]) -> None:
    """형식이 잘못된 새 조건 값은 거부한다."""
    # when·then: 잘못된 값이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


RETIRED_BANT_PARAMS = ["bant_budget", "bant_authority", "bant_need", "bant_timeline"]


@pytest.mark.parametrize("field", RETIRED_BANT_PARAMS)
def test_retired_bant_parameters_are_rejected(field: str) -> None:
    """폐지된 BANT 목록 필터 파라미터는 모르는 파라미터처럼 거절한다."""
    # when·then: 조용히 무시하지 않고 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams.model_validate({field: "5"})


def test_overdue_and_stale_default_to_false_and_reach_the_query() -> None:
    """overdue·stale은 기본이 False이고 위험 조건이 아니다."""
    # when: 파라미터 없이 조회 조건으로 바꾼다
    query = DealSearchParams().to_query(VIEWER)

    # then: 둘 다 False이고 위험 조건을 요구하지 않는다
    assert (query.overdue, query.stale) == (False, False)
    assert query.wants_risk() is False


@pytest.mark.parametrize("raw", ["true", "1", True])
def test_overdue_and_stale_true_reach_the_query(raw: object) -> None:
    """overdue·stale의 참 값은 조회 조건에 전달된다."""
    # when: 참 값을 각각·함께 조회 조건으로 바꾼다
    overdue = DealSearchParams.model_validate({"overdue": raw}).to_query(VIEWER)
    stale = DealSearchParams.model_validate({"stale": raw}).to_query(VIEWER)
    both = DealSearchParams.model_validate({"overdue": raw, "stale": raw}).to_query(VIEWER)

    # then: 준 조건만 켜진다
    assert (overdue.overdue, overdue.stale) == (True, False)
    assert (stale.overdue, stale.stale) == (False, True)
    assert (both.overdue, both.stale) == (True, True)


@pytest.mark.parametrize("raw", ["false", "0"])
def test_overdue_and_stale_false_values_are_no_condition(raw: str) -> None:
    """overdue·stale의 거짓 값은 조건 없음이다."""
    # when: 거짓 값을 조회 조건으로 바꾼다
    query = DealSearchParams.model_validate({"overdue": raw, "stale": raw}).to_query(VIEWER)

    # then: 위험 조건을 요구하지 않는다
    assert query.wants_risk() is False


@pytest.mark.parametrize("field", ["overdue", "stale"])
@pytest.mark.parametrize("raw", ["abc", "yes please", "2"])
def test_a_non_boolean_overdue_or_stale_is_rejected(field: str, raw: str) -> None:
    """불리언이 아닌 overdue·stale은 거부한다."""
    # when·then: 불리언이 아닌 값이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams.model_validate({field: raw})


def test_the_risk_filters_combine_with_mine_and_sort() -> None:
    """위험 필터는 내 Deal·정렬과 함께 쓸 수 있다."""
    # when: mine·stale·정렬을 함께 조회 조건으로 바꾼다
    query = DealSearchParams(mine=True, stale=True, sort="owner", order="desc").to_query(VIEWER)

    # then: 담당자 조건, stale, 정렬이 모두 담긴다
    assert query.owner_user_id == VIEWER
    assert query.stale is True
    assert (query.sort, query.order) == (DealSort.OWNER, SortOrder.DESC)


def test_the_new_conditions_keep_working_together_with_mine() -> None:
    """연도·분기·정렬은 내 Deal 조건과 함께 쓸 수 있다."""
    # when: mine·연도·분기·정렬을 함께 조회 조건으로 바꾼다
    query = DealSearchParams(mine=True, year=2026, quarter=[3], sort="name", order="asc").to_query(
        VIEWER
    )

    # then: 담당자 조건, 연도·분기, 정렬이 모두 담긴다
    assert query.owner_user_id == VIEWER
    assert (query.year, query.quarters) == (2026, frozenset({3}))
    assert (query.sort, query.order) == (DealSort.NAME, SortOrder.ASC)


@pytest.mark.parametrize("params", [{"bant_label": "x"}, {"sortBy": "name"}, {"direction": "asc"}])
def test_unknown_parameters_are_still_rejected(params: dict[str, object]) -> None:
    """모르는 파라미터는 여전히 거부한다."""
    # when·then: 모르는 파라미터를 주면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(**params)


@pytest.mark.parametrize("value", ["open", "done", "not_done", "closed"])
def test_deal_search_params_passes_next_action_status(value: str) -> None:
    """next_action_status 값이 조회 조건에 전달된다."""
    # when: 상태 값을 조회 조건으로 바꾼다
    query = DealSearchParams(next_action_status=value).to_query(VIEWER)

    # then: 같은 상태 필터가 담긴다
    assert query.next_action_status == NextActionStatusFilter(value)


def test_next_action_status_defaults_to_no_condition() -> None:
    """next_action_status를 주지 않으면 조건 없음이다."""
    # when: 파라미터 없이 조회 조건으로 바꾼다
    status = DealSearchParams().to_query(VIEWER).next_action_status

    # then: 조건이 없다
    assert status is None


@pytest.mark.parametrize("value", ["notDone", "DONE", "all", "", "close"])
def test_a_next_action_status_outside_the_whitelist_is_rejected(value: str) -> None:
    """허용 목록 밖의 next_action_status는 거부한다."""
    # when·then: 허용되지 않는 값이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(next_action_status=value)


def test_forecast_key_limits_are_named_constants_with_the_documented_values() -> None:
    """Forecast 키 상한 상수는 문서화된 값(100개, 50자)이다."""
    from app.web.schemas.deal import FORECAST_KEYS_MAX, STATUS_KEY_MAX  # noqa: PLC0415

    # when·then: 상수 값을 확인한다
    assert (FORECAST_KEYS_MAX, STATUS_KEY_MAX) == (100, 50)


# ---- Quarter 다중 선택 ----


def test_several_quarters_reach_the_query_as_a_set() -> None:
    """여러 분기는 집합으로 조회 조건에 전달된다."""
    # when: 분기 둘을 조회 조건으로 바꾼다
    query = DealSearchParams(year=2026, quarter=[3, 1]).to_query(VIEWER)

    # then: 두 분기가 집합에 담긴다
    assert query.quarters == frozenset({1, 3})


def test_a_repeated_quarter_equals_one() -> None:
    """같은 분기를 반복해도 하나와 같다."""
    # when: 같은 분기를 두 번 담아 조회 조건으로 바꾼다
    quarters = DealSearchParams(quarter=[1, 1]).to_query(VIEWER).quarters

    # then: 분기는 하나다
    assert quarters == frozenset({1})


def test_all_four_quarters_become_no_quarter_condition() -> None:
    """네 분기를 모두 고르면 분기 조건 없음이 된다."""
    # when: 1~4분기를 모두 담아 조회 조건으로 바꾼다
    quarters = DealSearchParams(year=2026, quarter=[1, 2, 3, 4]).to_query(VIEWER).quarters

    # then: 분기 조건이 없다
    assert quarters is None


def test_no_quarter_gives_no_quarter_condition() -> None:
    """분기를 주지 않으면 분기 조건 없음이다."""
    # when: 파라미터 없이 조회 조건으로 바꾼다
    quarters = DealSearchParams().to_query(VIEWER).quarters

    # then: 분기 조건이 없다
    assert quarters is None


@pytest.mark.parametrize("quarter", [[0], [5], [1, 5], [1, 2, 3, 4, 1]])
def test_a_bad_quarter_list_is_rejected(quarter: list[int]) -> None:
    """범위 밖이거나 5개를 넘는 분기 목록은 거부한다."""
    # when·then: 잘못된 분기 목록이면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(year=2026, quarter=quarter)


def test_four_quarter_values_are_accepted() -> None:
    """분기 값 네 개를 담은 파라미터는 허용한다."""
    # when: 네 분기를 담아 파라미터를 만든다
    params = DealSearchParams(year=2026, quarter=[1, 2, 3, 4])

    # then: 분기 목록이 그대로다
    assert params.quarter == [1, 2, 3, 4]


def test_a_scalar_quarter_is_no_longer_a_model_value() -> None:
    """분기 하나짜리 정수 값은 더 이상 모델 값이 아니다."""
    # when·then: 정수 분기를 주면 ValidationError가 난다
    with pytest.raises(ValidationError):
        DealSearchParams(year=2026, quarter=2)
