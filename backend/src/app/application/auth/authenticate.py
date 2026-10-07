from typing import TYPE_CHECKING

from app.application.auth.tokens import hash_token
from app.domain.auth.errors import AuthenticationError

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal


class Authenticate:
    """세션 토큰으로 현재 사용자를 찾는다. 없거나 만료·폐기됐으면 AuthenticationError."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, token: str | None) -> Principal:
        if not token:
            raise AuthenticationError("로그인이 필요합니다")
        async with self._uow_factory() as uow:
            session = await uow.sessions.get_by_token_hash(hash_token(token))
        if session is None or not session.is_active(self._clock.now()):
            raise AuthenticationError("로그인이 필요합니다")
        return session.principal
