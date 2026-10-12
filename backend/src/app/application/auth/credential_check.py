from typing import TYPE_CHECKING

from app.application.auth.messages import LOGIN_FAILED
from app.application.ports.directory import DirectoryError, InvalidCredentialsError
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.application.auth.deps import AuthDeps
    from app.application.ports.directory import DirectoryUser
    from app.domain.auth.credentials import Password
    from app.domain.directory.settings import DirectorySettings


def parse_login_id(raw: str) -> LoginId:
    """형식이 잘못된 아이디도 다른 실패와 같은 문구로 거부한다(AD에 보내지 않는다)."""
    try:
        return LoginId(raw)
    except InvalidValueError:
        raise AuthenticationError(LOGIN_FAILED) from None


async def verify_credentials(
    deps: AuthDeps,
    settings: DirectorySettings,
    login_id: LoginId,
    password: Password,
    client_ip: str,
) -> DirectoryUser:
    """AD에 인증한다. 자격증명 실패는 LOGIN_FAILED(선점=실패 1회), 연결 불가는 선점 반환."""
    try:
        return await deps.directory.authenticate(settings, login_id, password)
    except InvalidCredentialsError:
        raise AuthenticationError(LOGIN_FAILED) from None
    except DirectoryError:
        await deps.throttle.release(login_id, client_ip)
        raise
