from typing import TYPE_CHECKING

from app.application.auth.dev_login import DEV_SUBJECT_PREFIX
from app.application.auth.tokens import hash_token
from app.domain.auth.credentials import LoginId
from app.domain.auth.errors import AuthenticationError
from app.domain.common.errors import InvalidValueError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal

_LOGIN_REQUIRED = "로그인이 필요합니다"


class Authenticate:
    """세션 토큰으로 현재 사용자를 찾는다. 역할·프로필은 매 요청 users 표에서 읽는다.

    dev 세션(subject가 `dev:`로 시작)은 허용된 경우에만 users 표 없이 통과한다.
    """

    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, *, allow_dev_sessions: bool
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._allow_dev_sessions = allow_dev_sessions

    async def execute(self, token: str | None) -> Principal:
        if not token:
            raise AuthenticationError(_LOGIN_REQUIRED)
        async with self._uow_factory() as uow:
            session = await uow.sessions.get_by_token_hash(hash_token(token))
            if session is None or not session.is_active(self._clock.now()):
                raise AuthenticationError(_LOGIN_REQUIRED)
            subject = session.principal.subject
            if subject.startswith(DEV_SUBJECT_PREFIX):
                if not self._allow_dev_sessions:
                    raise AuthenticationError(_LOGIN_REQUIRED)
                return session.principal
            user = await uow.users.get_active_by_login_id(_parse(subject))
        if user is None:
            raise AuthenticationError(_LOGIN_REQUIRED)
        return user.to_principal()


def _parse(subject: str) -> LoginId:
    try:
        return LoginId(subject)
    except InvalidValueError:
        raise AuthenticationError(_LOGIN_REQUIRED) from None
