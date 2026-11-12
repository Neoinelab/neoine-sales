"""코드 값 객체와 상수 (CD-003 잠금 코드 5개, CD-019 key 형식, CD-R1 종류·결과)."""

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
    """코드 종류는 status, forecast 두 가지다."""
    # when: 종류 값을 모은다
    kinds = [kind.value for kind in CodeKind]

    # then: status, forecast 순서다
    assert kinds == ["status", "forecast"]


def test_forecast_outcomes_are_open_won_and_lost() -> None:
    """Forecast 결과는 open, won, lost 세 가지다."""
    # when: 결과 값을 모은다
    outcomes = {outcome.value for outcome in ForecastOutcome}

    # then: open, won, lost다
    assert outcomes == {"open", "won", "lost"}


def test_length_limits_are_fixed() -> None:
    """이름은 50자, 확률 힌트는 20자까지다."""
    # when·then: 길이 상수를 읽으면 문서의 값이다
    assert CODE_NAME_MAX == 50
    assert PROBABILITY_HINT_MAX == 20


def test_locked_keys_are_exactly_the_five_system_codes() -> None:
    """잠금 key는 정확히 다섯 개(Status 2, Forecast 3)다.

    테스트 코드: CD-003
    """
    # when: 종류별 잠금 key를 읽는다
    locked = dict(LOCKED_KEYS)

    # then: Status prospecting·contract_completed, Forecast pipeline·won·lost뿐이다
    assert locked == {
        CodeKind.STATUS: frozenset({"prospecting", "contract_completed"}),
        CodeKind.FORECAST: frozenset({"pipeline", "won", "lost"}),
    }


@pytest.mark.parametrize("value", ["a", "prospecting", "code_1", "a1_b2", "x" * 50])
def test_code_key_accepts_lowercase_letters_digits_and_underscores(value: str) -> None:
    """key는 소문자로 시작하고 소문자·숫자·밑줄로 50자까지 받는다.

    테스트 코드: CD-019
    """
    # when: key를 만든다
    key = CodeKey(value)

    # then: 값이 그대로다
    assert key.value == value


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
    """key 형식에 맞지 않는 값은 거절한다.

    테스트 코드: CD-019
    """
    # when: 형식이 틀린 key를 만든다
    with pytest.raises(InvalidValueError):
        CodeKey(value)

    # then: 값이 잘못되었다는 오류가 난다(위 with 블록)


def test_code_keys_with_same_value_are_equal() -> None:
    """같은 값의 key는 같고 다른 값은 다르다."""
    # when·then: key를 비교하면 값이 같을 때만 같다
    assert CodeKey("best") == CodeKey("best")
    assert CodeKey("best") != CodeKey("commit")
