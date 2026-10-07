from typing import TYPE_CHECKING

from app.application.auth.tokens import hash_token

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWorkFactory


class Logout:
    """세션을 폐기한다. 이미 없거나 폐기된 세션이어도 오류 없이 끝난다(멱등)."""

    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def execute(self, token: str | None) -> None:
        if not token:
            return
        async with self._uow_factory() as uow:
            session = await uow.sessions.get_by_token_hash(hash_token(token))
            if session is None or session.revoked_at is not None:
                return
            session.revoke(self._clock.now())
            await uow.sessions.update(session)
            await uow.commit()
