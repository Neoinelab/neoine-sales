"""UnitOfWork Port의 SQLAlchemy 구현. 블록을 열 때마다 새 세션(트랜잭션)을 만든다."""

from typing import TYPE_CHECKING, Self

from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.deal_stage_change_repository import SqlDealStageChangeRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from app.infra.db.session_repository import SqlSessionRepository

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlUnitOfWork:
    customers: SqlCustomerRepository
    partners: SqlPartnerRepository
    deals: SqlDealRepository
    deal_actions: SqlDealActionRepository
    deal_stage_changes: SqlDealStageChangeRepository
    sessions: SqlSessionRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.customers = SqlCustomerRepository(self._session)
        self.partners = SqlPartnerRepository(self._session)
        self.deals = SqlDealRepository(self._session)
        self.deal_actions = SqlDealActionRepository(self._session)
        self.deal_stage_changes = SqlDealStageChangeRepository(self._session)
        self.sessions = SqlSessionRepository(self._session)
        return self

    async def __aexit__(self, *exc: object) -> None:
        try:
            await self._session.rollback()  # commit하지 않은 변경은 버린다(commit 뒤에는 변경 없음)
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


def sql_unit_of_work_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[[], SqlUnitOfWork]:
    """호출할 때마다 새 UoW를 만드는 팩토리. UoW는 세션을 들고 있어 요청 간에 공유하지 않는다."""
    return lambda: SqlUnitOfWork(session_factory)
