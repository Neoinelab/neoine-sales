"""WrongCurrentPasswordError (AC-11): 422 invalid-value로 매핑되는 InvalidValueError의 하위 종류."""

from app.domain.auth.errors import WeakPasswordError, WrongCurrentPasswordError
from app.domain.common.errors import InvalidValueError


def test_wrong_current_password_is_an_invalid_value_error() -> None:
    error = WrongCurrentPasswordError("현재 비밀번호가 올바르지 않습니다.")

    assert isinstance(error, InvalidValueError)
    assert str(error) == "현재 비밀번호가 올바르지 않습니다."


def test_weak_password_error_is_an_invalid_value_error_but_not_a_wrong_current_password() -> None:
    error = WeakPasswordError("비밀번호는 8자 이상이어야 합니다")

    assert isinstance(error, InvalidValueError)
    assert not isinstance(error, WrongCurrentPasswordError)
