"""폐지된 개발용 로그인(2026-11-03)이 쓰던 `dev-` 접두사 아이디 규칙.

이 접두사의 아이디는 새로 등록할 수 없고 로그인도 거부한다.
"""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId

RESERVED_PREFIX = "dev-"


def is_retired_dev_login_id(login_id: LoginId) -> bool:
    """`dev-` 접두사(소문자 정규화 뒤)면 True."""
    return login_id.value.startswith(RESERVED_PREFIX)


def ensure_not_reserved_login_id(account: LoginId) -> None:
    """개발 로그인 전용 아이디로는 사용자를 등록할 수 없다(InvalidValueError)."""
    if is_retired_dev_login_id(account):
        raise InvalidValueError(f"개발 로그인 전용 아이디는 등록할 수 없습니다: {account.value}")
