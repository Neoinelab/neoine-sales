"""Deal 목록 쿼리의 month(P6 R1 AC-12): 1~12, DealQuery로 전달, quarter와 함께면 도메인 오류."""

import pytest
from pydantic import ValidationError

from app.domain.common.errors import InvalidValueError
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


def test_year_and_month_reach_the_query() -> None:
    query = DealSearchParams(year=2026, month=3).to_query(VIEWER)

    assert (query.year, query.quarters, query.month) == (2026, None, 3)


def test_month_defaults_to_none() -> None:
    assert DealSearchParams().to_query(VIEWER).month is None


@pytest.mark.parametrize("month", [0, 13])
def test_month_outside_one_to_twelve_is_a_validation_error(month: int) -> None:
    with pytest.raises(ValidationError) as caught:
        DealSearchParams(year=2026, month=month)

    # 모르는 필드(extra_forbidden)가 아니라 범위 위반이어야 한다
    assert {e["type"] for e in caught.value.errors()} <= {"greater_than_equal", "less_than_equal"}
    assert caught.value.errors()[0]["loc"] == ("month",)


def test_quarter_and_month_together_raise_invalid_value_on_conversion() -> None:
    params = DealSearchParams(year=2026, quarter=[1], month=1)

    with pytest.raises(InvalidValueError):
        params.to_query(VIEWER)


def test_several_quarters_and_month_together_raise_invalid_value_on_conversion() -> None:
    params = DealSearchParams(year=2026, quarter=[1, 3], month=2)

    with pytest.raises(InvalidValueError):
        params.to_query(VIEWER)


def test_all_four_quarters_with_a_month_convert_to_a_month_only_query() -> None:
    query = DealSearchParams(year=2026, quarter=[1, 2, 3, 4], month=2).to_query(VIEWER)

    assert (query.quarters, query.month) == (None, 2)
