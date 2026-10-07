from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import uuid4

from app.application.auth.tokens import hash_token, new_token
from app.domain.auth.session import AuthSession, SessionId

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
        session = AuthSession(
            id=SessionId(uuid4()), principal=principal, created_at=now, expires_at=now + self._ttl
        )
        async with self._uow_factory() as uow:
            await uow.sessions.add(session, hash_token(token))
            await uow.commit()
        return IssuedSession(token, session.expires_at, principal)
