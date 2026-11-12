"""Deal 목록 쿼리의 month: 1~12, DealQuery로 전달, quarter와 함께면 도메인 오류."""

import pytest
from pydantic import ValidationError

from app.domain.common.errors import InvalidValueError
from app.web.schemas.deal import DealSearchParams
from tests.support.user_ids import uid

VIEWER = uid("viewer")


def test_year_and_month_reach_the_query() -> None:
    """연도와 월이 DealQuery까지 전달되는지 확인한다."""
    # when: 연도와 월을 준 파라미터를 쿼리로 바꾼다
    query = DealSearchParams(year=2026, month=3).to_query(VIEWER)

    # then: 연도와 월이 담기고 분기는 없다
    assert (query.year, query.quarters, query.month) == (2026, None, 3)


def test_month_defaults_to_none() -> None:
    """월을 생략하면 쿼리의 월이 None인지 확인한다."""
    # when: 월 없는 파라미터를 쿼리로 바꾼다
    result = DealSearchParams().to_query(VIEWER).month
    # then: 월이 None이다
    assert result is None


@pytest.mark.parametrize("month", [0, 13])
def test_month_outside_one_to_twelve_is_a_validation_error(month: int) -> None:
    """1~12 밖의 월은 검증 오류인지 확인한다."""
    # when: 범위 밖 월로 파라미터를 만든다
    with pytest.raises(ValidationError) as caught:
        DealSearchParams(year=2026, month=month)

    # then: 범위 위반 오류이고 위치가 month다
    # 모르는 필드(extra_forbidden)가 아니라 범위 위반이어야 한다
    assert {e["type"] for e in caught.value.errors()} <= {"greater_than_equal", "less_than_equal"}
    assert caught.value.errors()[0]["loc"] == ("month",)


def test_quarter_and_month_together_raise_invalid_value_on_conversion() -> None:
    """분기와 월을 함께 주면 변환 때 InvalidValueError인지 확인한다."""
    # given: 분기와 월을 함께 준 파라미터가 있다
    params = DealSearchParams(year=2026, quarter=[1], month=1)

    # when·then: 쿼리로 바꾸면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        params.to_query(VIEWER)


def test_several_quarters_and_month_together_raise_invalid_value_on_conversion() -> None:
    """여러 분기와 월을 함께 주면 변환 때 InvalidValueError인지 확인한다."""
    # given: 여러 분기와 월을 함께 준 파라미터가 있다
    params = DealSearchParams(year=2026, quarter=[1, 3], month=2)

    # when·then: 쿼리로 바꾸면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        params.to_query(VIEWER)


def test_all_four_quarters_with_a_month_convert_to_a_month_only_query() -> None:
    """네 분기 전체와 월은 월만 있는 쿼리로 바뀌는지 확인한다."""
    # when: 네 분기 전체와 월을 준 파라미터를 쿼리로 바꾼다
    query = DealSearchParams(year=2026, quarter=[1, 2, 3, 4], month=2).to_query(VIEWER)

    # then: 분기 조건은 없고 월만 남는다
    assert (query.quarters, query.month) == (None, 2)
