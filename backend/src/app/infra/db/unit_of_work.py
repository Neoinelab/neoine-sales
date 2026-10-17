"""UnitOfWork Port의 SQLAlchemy 구현. 블록을 열 때마다 새 세션(트랜잭션)을 만든다."""

from typing import TYPE_CHECKING, Self

from app.infra.db.alert_settings_repository import SqlAlertSettingsRepository
from app.infra.db.attachment_repository import SqlAttachmentRepository
from app.infra.db.bant_label_repository import SqlBantLabelRepository
from app.infra.db.code_repository import SqlCodeRepository
from app.infra.db.contact_repository import SqlContactRepository
from app.infra.db.deal_action_repository import SqlDealActionRepository
from app.infra.db.deal_history_repository import SqlDealHistoryRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.directory_settings_repository import SqlDirectorySettingsRepository
from app.infra.db.login_failure_repository import SqlLoginFailureRepository
from app.infra.db.session_repository import SqlSessionRepository
from app.infra.db.storage_settings_repository import SqlStorageSettingsRepository
from app.infra.db.user_repository import SqlUserRepository

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class SqlUnitOfWork:
    contacts: SqlContactRepository
    deals: SqlDealRepository
    deal_actions: SqlDealActionRepository
    deal_history: SqlDealHistoryRepository
    sessions: SqlSessionRepository
    users: SqlUserRepository
    login_failures: SqlLoginFailureRepository
    directory_settings: SqlDirectorySettingsRepository
    storage_settings: SqlStorageSettingsRepository
    codes: SqlCodeRepository
    bant_labels: SqlBantLabelRepository
    attachments: SqlAttachmentRepository
    alert_settings: SqlAlertSettingsRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def __aenter__(self) -> Self:
        self._session = self._session_factory()
        self.contacts = SqlContactRepository(self._session)
        self.deals = SqlDealRepository(self._session)
        self.deal_actions = SqlDealActionRepository(self._session)
        self.deal_history = SqlDealHistoryRepository(self._session)
        self.sessions = SqlSessionRepository(self._session)
        self.users = SqlUserRepository(self._session)
        self.login_failures = SqlLoginFailureRepository(self._session)
        self.directory_settings = SqlDirectorySettingsRepository(self._session)
        self.storage_settings = SqlStorageSettingsRepository(self._session)
        self.codes = SqlCodeRepository(self._session)
        self.bant_labels = SqlBantLabelRepository(self._session)
        self.attachments = SqlAttachmentRepository(self._session)
        self.alert_settings = SqlAlertSettingsRepository(self._session)
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
