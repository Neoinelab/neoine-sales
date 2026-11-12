"""AlertThresholds: 미업데이트 기준(일)은 1~365의 정수, 기본 14."""

from typing import Any

import pytest

from app.domain.alert.thresholds import (
    STALE_DAYS_DEFAULT,
    STALE_DAYS_MAX,
    STALE_DAYS_MIN,
    AlertThresholds,
)
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

RANGE_MESSAGE = "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."


def test_default_is_fourteen_days() -> None:
    """기본 경고 기준은 14일이다.

    테스트 코드: RK-022
    """
    # when: 기본값을 만든다
    assert AlertThresholds.default() == AlertThresholds(stale_days=14)
    # then: 14일이다
    assert STALE_DAYS_DEFAULT == 14


def test_bounds_are_one_and_365() -> None:
    """경고 기준의 범위는 1~365일이다.

    테스트 코드: RK-045
    """
    # when·then: 범위 상수를 읽는다 → 1과 365다
    assert (STALE_DAYS_MIN, STALE_DAYS_MAX) == (1, 365)


@pytest.mark.parametrize("days", [1, 7, 14, 365])
def test_values_inside_the_range_are_accepted(days: int) -> None:
    """범위 안의 정수는 받아들인다.

    테스트 코드: RK-045
    """
    # when: 범위 안의 값으로 만든다
    stale_days = AlertThresholds(stale_days=days).stale_days
    # then: 그 값이 그대로 담긴다
    assert stale_days == days


@pytest.mark.parametrize("days", [0, 366, -1, 10_000])
def test_values_outside_the_range_are_rejected_with_the_fixed_message(days: int) -> None:
    """범위 밖 정수는 고정 문구로 거절한다.

    테스트 코드: RK-046
    """
    # when·then: 범위 밖 값으로 만든다 → InvalidValueError(범위 문구)다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=days)


@pytest.mark.parametrize("value", [True, False])
def test_bool_is_rejected_even_though_it_is_an_int(value: bool) -> None:
    """bool은 int여도 거절한다.

    테스트 코드: RK-047
    """
    # when·then: bool로 만든다 → InvalidValueError(범위 문구)다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=value)


@pytest.mark.parametrize("value", [7.0, 7.5, "7", None])
def test_non_integers_are_rejected(value: Any) -> None:  # noqa: ANN401 - 잘못된 타입을 일부러 넣는다
    """소수·문자열·None은 거절한다.

    테스트 코드: RK-047
    """
    # when·then: 정수가 아닌 값으로 만든다 → InvalidValueError(범위 문구)다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=value)


def test_equal_thresholds_compare_equal() -> None:
    """같은 일수의 경고 기준은 같고 다른 일수는 다르다."""
    # when: 두 값을 비교한다
    assert AlertThresholds(stale_days=7) == AlertThresholds(stale_days=7)
    # then: 7일끼리는 같고 7일과 8일은 다르다
    assert AlertThresholds(stale_days=7) != AlertThresholds(stale_days=8)
