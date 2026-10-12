"""사용자·세션 상태를 읽는 도우미(S5 검증용). Fake/실제 UoW 어느 쪽에나 쓴다."""

from typing import TYPE_CHECKING

from app.application.auth.tokens import hash_token
from tests.factories import NOW

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWorkFactory


async def session_is_active(
    uow_factory: UnitOfWorkFactory, token: str, now: datetime = NOW
) -> bool:
    """세션 토큰이 저장소에서 아직 쓸 수 있는 상태인지(폐기·만료 아님)."""
    async with uow_factory() as uow:
        session = await uow.sessions.get_by_token_hash(hash_token(token))
    return session is not None and session.is_active(now)


async def active_logins(uow_factory: UnitOfWorkFactory) -> list[str]:
    async with uow_factory() as uow:
        users = await uow.users.list_active(limit=100)
    return sorted(u.login_id.value for u in users)
