"""ForecastOutcomeFilter / DealQuery.forecast_outcome (Dashboard).

필터 값이 Forecast 코드 outcome 집합으로 바뀌는 규칙과, `forecast_key`와 함께 지정할 수 있다는 점만
본다. 실제 AND 결합은 저장소 계약(`test_deal_forecast_outcome_contract.py`)이 검증한다.
"""

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.code.values import ForecastOutcome


def test_not_lost_filter_means_open_and_won() -> None:
    """not_lost 필터는 Open과 Won outcome을 뜻한다."""
    # when: not_lost 필터의 outcome 집합을 얻는다
    outcomes = set(ForecastOutcomeFilter.NOT_LOST.outcomes())

    # then: Open과 Won이다
    assert outcomes == {ForecastOutcome.OPEN, ForecastOutcome.WON}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("open", ForecastOutcome.OPEN),
        ("won", ForecastOutcome.WON),
        ("lost", ForecastOutcome.LOST),
    ],
)
def test_single_outcome_filters_map_to_one_outcome(value: str, expected: ForecastOutcome) -> None:
    """open·won·lost 필터는 각각 outcome 하나만 뜻한다."""
    # when: 필터 값의 outcome 집합을 얻는다
    outcomes = tuple(ForecastOutcomeFilter(value).outcomes())

    # then: 해당 outcome 하나다
    assert outcomes == (expected,)


def test_the_filter_values_are_exactly_the_four_documented_strings() -> None:
    """필터 값은 문서의 네 문자열뿐이다."""
    # when: 필터의 모든 값을 모은다
    values = {f.value for f in ForecastOutcomeFilter}

    # then: open, won, lost, not_lost 넷이다
    assert values == {"open", "won", "lost", "not_lost"}


def test_an_unknown_filter_value_is_rejected() -> None:
    """알 수 없는 필터 값은 거절된다."""
    # when·then: 정의에 없는 값으로 만들면 ValueError다
    with pytest.raises(ValueError, match="foo"):
        ForecastOutcomeFilter("foo")


def test_deal_query_defaults_to_no_outcome_filter() -> None:
    """DealQuery는 outcome 필터를 기본으로 지정하지 않는다."""
    # when: 조건 없이 DealQuery를 만든다
    query = DealQuery()

    # then: outcome 필터는 없다
    assert query.forecast_outcome is None


def test_deal_query_accepts_forecast_outcome_with_forecast_keys() -> None:
    """DealQuery는 forecast_key와 outcome을 함께 받을 수 있다."""
    # when: 둘을 함께 지정해 DealQuery를 만든다
    query = DealQuery(
        forecast_keys=frozenset({"commit"}), forecast_outcome=ForecastOutcomeFilter.OPEN
    )

    # then: 두 값이 모두 보존된다
    assert query.forecast_keys == frozenset({"commit"})
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN
