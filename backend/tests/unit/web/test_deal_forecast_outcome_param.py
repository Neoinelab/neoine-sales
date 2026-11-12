"""Deal 목록 `forecast_outcome` 쿼리 파라미터 (Dashboard): 4값만 받고 DealQuery로 전달한다."""

import pytest
from pydantic import ValidationError

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


@pytest.mark.parametrize("value", ["open", "won", "lost", "not_lost"])
def test_every_documented_outcome_reaches_the_query(value: str) -> None:
    """문서의 네 outcome 값은 DealQuery까지 전달된다."""
    # when: outcome 값으로 쿼리를 만든다
    query = DealSearchParams(forecast_outcome=value).to_query(VIEWER)

    # then: 같은 필터 값이 담긴다
    assert query.forecast_outcome is ForecastOutcomeFilter(value)


def test_the_outcome_defaults_to_none() -> None:
    """outcome을 주지 않으면 필터는 없다."""
    # when: outcome 없이 쿼리를 만든다
    query = DealSearchParams().to_query(VIEWER)

    # then: outcome 필터는 None이다
    assert query.forecast_outcome is None


@pytest.mark.parametrize("value", ["foo", "", "OPEN", "not-lost", "all"])
def test_deal_search_params_reject_unknown_forecast_outcome(value: str) -> None:
    """알 수 없는 outcome 값은 검증 오류다."""
    # when·then: 정의에 없는 값을 주면 ValidationError다
    with pytest.raises(ValidationError):
        DealSearchParams(forecast_outcome=value)


def test_the_outcome_combines_with_forecast_key_in_one_query() -> None:
    """forecast_key와 outcome은 한 쿼리에 함께 담긴다."""
    # when: 둘을 함께 주어 쿼리를 만든다
    query = DealSearchParams(forecast_key=["commit"], forecast_outcome="open").to_query(VIEWER)

    # then: 두 조건이 모두 담긴다
    assert query.forecast_keys == frozenset({"commit"})
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN
