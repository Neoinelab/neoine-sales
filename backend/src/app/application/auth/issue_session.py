from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.application.auth.messages import LOGIN_FAILED
from app.application.auth.tokens import hash_token, new_token
from app.application.ids import new_session_id
from app.domain.auth.errors import AuthenticationError
from app.domain.auth.session import AuthSession
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.auth.principal import Principal


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str  # 브라우저에 쿠키로 줄 값. 저장소에는 해시만 남는다
    expires_at: datetime
    principal: Principal


class IssueSession:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, ttl: timedelta) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ttl = ttl

    async def execute(self, principal: Principal) -> IssuedSession:
        now = self._clock.now()
        token = new_token()
        try:
            async with self._uow_factory() as uow:
                session = AuthSession(
                    id=await new_session_id(uow.ids),
                    principal=principal,
                    created_at=now,
                    expires_at=now + self._ttl,
                )
                await uow.sessions.add(session, hash_token(token))
                await uow.commit()
        except UserNotFoundError:  # 발급 직전 사용자가 삭제됨(세션 FK 위반)
            raise AuthenticationError(LOGIN_FAILED) from None
        return IssuedSession(token, session.expires_at, principal)
