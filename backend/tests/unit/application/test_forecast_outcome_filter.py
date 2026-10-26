"""ForecastOutcomeFilter / DealQuery.forecast_outcome (Dashboard AC-9).

필터 값이 Forecast 코드 outcome 집합으로 바뀌는 규칙과, `forecast_key`와 함께 지정할 수 있다는 점만
본다. 실제 AND 결합은 저장소 계약(`test_deal_forecast_outcome_contract.py`)이 검증한다.
"""

import pytest

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.code.values import ForecastOutcome


def test_not_lost_filter_means_open_and_won() -> None:
    assert set(ForecastOutcomeFilter.NOT_LOST.outcomes()) == {
        ForecastOutcome.OPEN,
        ForecastOutcome.WON,
    }


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("open", ForecastOutcome.OPEN),
        ("won", ForecastOutcome.WON),
        ("lost", ForecastOutcome.LOST),
    ],
)
def test_single_outcome_filters_map_to_one_outcome(value: str, expected: ForecastOutcome) -> None:
    assert tuple(ForecastOutcomeFilter(value).outcomes()) == (expected,)


def test_the_filter_values_are_exactly_the_four_documented_strings() -> None:
    assert {f.value for f in ForecastOutcomeFilter} == {"open", "won", "lost", "not_lost"}


def test_an_unknown_filter_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="foo"):
        ForecastOutcomeFilter("foo")


def test_deal_query_defaults_to_no_outcome_filter() -> None:
    assert DealQuery().forecast_outcome is None


def test_deal_query_accepts_forecast_outcome_with_forecast_keys() -> None:
    query = DealQuery(
        forecast_keys=frozenset({"commit"}), forecast_outcome=ForecastOutcomeFilter.OPEN
    )

    assert query.forecast_keys == frozenset({"commit"})
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN
