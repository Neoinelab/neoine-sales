"""비밀번호 요청 필드 공통: 마스킹된 SecretStr -> 도메인 Password, 위치가 붙는 입력 오류."""

from pydantic import SecretStr

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError


class InvalidFieldError(Exception):
    """요청 본문의 특정 필드 값이 잘못됐다(422 invalid-value + errors[].location)."""

    def __init__(self, location: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.location = location
        self.message = message


def to_new_password(secret: SecretStr, field: str) -> Password:
    """빈 값·NUL은 해당 필드의 422로 알린다(로그인과 달리 401이 아니다)."""
    try:
        return Password(secret.get_secret_value())
    except InvalidValueError as error:
        raise InvalidFieldError((field,), str(error)) from None
