from typing import TYPE_CHECKING

from app.application.auth.tokens import hash_token
from app.domain.auth.errors import AuthenticationError
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal

_LOGIN_REQUIRED = "로그인이 필요합니다"


class Authenticate:
    """세션 토큰으로 현재 사용자를 찾는다. 역할·프로필은 매 요청 users 표에서 읽는다.

    세션은 users.id를 가리키므로 퇴사했거나 삭제된 사용자의 토큰은 항상 거부된다.
    """

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, token: str | None) -> Principal:
        if not token:
            raise AuthenticationError(_LOGIN_REQUIRED)
        async with self._uow_factory() as uow:
            session = await uow.sessions.get_by_token_hash(hash_token(token))
            if session is None or not session.is_active(self._clock.now()):
                raise AuthenticationError(_LOGIN_REQUIRED)
            try:
                user = await uow.users.get(session.principal.user_id)
            except UserNotFoundError:
                raise AuthenticationError(_LOGIN_REQUIRED) from None
        if not user.is_active:
            raise AuthenticationError(_LOGIN_REQUIRED)
        return user.to_principal()
