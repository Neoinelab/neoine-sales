"""Deal 목록 `forecast_outcome` 쿼리 파라미터 (Dashboard AC-9): 4값만 받고 DealQuery로 전달한다."""

import pytest
from pydantic import ValidationError

from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


@pytest.mark.parametrize("value", ["open", "won", "lost", "not_lost"])
def test_every_documented_outcome_reaches_the_query(value: str) -> None:
    query = DealSearchParams(forecast_outcome=value).to_query(VIEWER)

    assert query.forecast_outcome is ForecastOutcomeFilter(value)


def test_the_outcome_defaults_to_none() -> None:
    assert DealSearchParams().to_query(VIEWER).forecast_outcome is None


@pytest.mark.parametrize("value", ["foo", "", "OPEN", "not-lost", "all"])
def test_deal_search_params_reject_unknown_forecast_outcome(value: str) -> None:
    with pytest.raises(ValidationError):
        DealSearchParams(forecast_outcome=value)


def test_the_outcome_combines_with_forecast_key_in_one_query() -> None:
    query = DealSearchParams(forecast_key="commit", forecast_outcome="open").to_query(VIEWER)

    assert query.forecast_key == "commit"
    assert query.forecast_outcome is ForecastOutcomeFilter.OPEN
