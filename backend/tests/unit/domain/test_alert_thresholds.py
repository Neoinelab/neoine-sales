"""AlertThresholds(P3 AC-05·07): 미업데이트 기준(일)은 1~365의 정수, 기본 14."""

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
    assert AlertThresholds.default() == AlertThresholds(stale_days=14)
    assert STALE_DAYS_DEFAULT == 14


def test_bounds_are_one_and_365() -> None:
    assert (STALE_DAYS_MIN, STALE_DAYS_MAX) == (1, 365)


@pytest.mark.parametrize("days", [1, 7, 14, 365])
def test_values_inside_the_range_are_accepted(days: int) -> None:
    assert AlertThresholds(stale_days=days).stale_days == days


@pytest.mark.parametrize("days", [0, 366, -1, 10_000])
def test_values_outside_the_range_are_rejected_with_the_fixed_message(days: int) -> None:
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=days)


@pytest.mark.parametrize("value", [True, False])
def test_bool_is_rejected_even_though_it_is_an_int(value: bool) -> None:
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=value)


@pytest.mark.parametrize("value", [7.0, 7.5, "7", None])
def test_non_integers_are_rejected(value: Any) -> None:  # noqa: ANN401 - 잘못된 타입을 일부러 넣는다
    with raises_with(InvalidValueError, RANGE_MESSAGE):
        AlertThresholds(stale_days=value)


def test_equal_thresholds_compare_equal() -> None:
    assert AlertThresholds(stale_days=7) == AlertThresholds(stale_days=7)
    assert AlertThresholds(stale_days=7) != AlertThresholds(stale_days=8)
