"""코드 값 객체와 상수 (AC-01 종류·outcome, AC-03 key 형식, AC-07 잠금 코드 5개)."""

import pytest
from app.domain.code.values import (
    CODE_NAME_MAX,
    LOCKED_KEYS,
    PROBABILITY_HINT_MAX,
    CodeKey,
    CodeKind,
    ForecastOutcome,
)

from app.domain.common.errors import InvalidValueError


def test_code_kinds_are_status_and_forecast() -> None:
    assert [kind.value for kind in CodeKind] == ["status", "forecast"]


def test_forecast_outcomes_are_open_won_and_lost() -> None:
    assert {outcome.value for outcome in ForecastOutcome} == {"open", "won", "lost"}


def test_length_limits_are_fixed() -> None:
    assert CODE_NAME_MAX == 50
    assert PROBABILITY_HINT_MAX == 20


def test_locked_keys_are_exactly_the_five_system_codes() -> None:
    assert dict(LOCKED_KEYS) == {
        CodeKind.STATUS: frozenset({"prospecting", "contract_completed"}),
        CodeKind.FORECAST: frozenset({"pipeline", "won", "lost"}),
    }


@pytest.mark.parametrize("value", ["a", "prospecting", "code_1", "a1_b2", "x" * 50])
def test_code_key_accepts_lowercase_letters_digits_and_underscores(value: str) -> None:
    assert CodeKey(value).value == value


@pytest.mark.parametrize(
    "value",
    ["", "Upper", "1abc", "_abc", "has space", "dash-ed", "한글", "x" * 51],
    ids=[
        "empty",
        "upper",
        "digit-first",
        "underscore-first",
        "space",
        "dash",
        "korean",
        "51-chars",
    ],
)
def test_code_key_rejects_other_shapes(value: str) -> None:
    with pytest.raises(InvalidValueError):
        CodeKey(value)


def test_code_keys_with_same_value_are_equal() -> None:
    assert CodeKey("best") == CodeKey("best")
    assert CodeKey("best") != CodeKey("commit")
