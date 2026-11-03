"""폐지된 개발용 로그인(2026-11-03)이 쓰던 예약 아이디 규칙.

예약 아이디는 `dev-admin`·`dev-sales`·`dev-user` 셋뿐이다(정규화 값 정확히 일치).
`dev-qa` 같은 다른 `dev-` 아이디는 일반 아이디다.
예약 아이디는 새로 등록할 수 없고 로그인도 거부한다.
"""

from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.domain.auth.credentials import LoginId

RESERVED_LOGIN_IDS = frozenset({"dev-admin", "dev-sales", "dev-user"})


def is_retired_dev_login_id(login_id: LoginId) -> bool:
    """정규화된 값이 예약 아이디 셋 중 하나면 True."""
    return login_id.value in RESERVED_LOGIN_IDS


def ensure_not_reserved_login_id(account: LoginId) -> None:
    """개발 로그인 전용 아이디로는 사용자를 등록할 수 없다(InvalidValueError)."""
    if is_retired_dev_login_id(account):
        raise InvalidValueError(f"개발 로그인 전용 아이디는 등록할 수 없습니다: {account.value}")
