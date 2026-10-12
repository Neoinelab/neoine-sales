"""Composition Root: Port와 구현체를 연결하고 유스케이스를 만들어 준다(UseCaseProvider 구현)."""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.get_customer import GetCustomer
from app.application.customer.list_customers import ListCustomers
from app.application.customer.register_customer import RegisterCustomer
from app.application.customer.update_customer import UpdateCustomer
from app.application.deal.change_stage import ChangeDealStage
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.get_deal_by_code import GetDealByCode
from app.application.deal.get_pipeline import GetDealPipeline
from app.application.deal.list_deals import ListDeals
from app.application.deal.list_stage_changes import ListDealStageChanges
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.search_deal_actions import SearchDealActions
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.application.partner.delete_partner import DeletePartner
from app.application.partner.get_partner import GetPartner
from app.application.partner.list_partners import ListPartners
from app.application.partner.register_partner import RegisterPartner
from app.application.partner.update_partner import UpdatePartner
from app.container_admin import AdminAssembly
from app.container_auth import AuthAssembly
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from app.infra.system_clock import SystemClock

if TYPE_CHECKING:
    from app.application.auth.auth_status import GetAuthStatus
    from app.application.auth.authenticate import Authenticate
    from app.application.auth.dev_login import DevLogin
    from app.application.auth.directory_login import DirectoryLogin
    from app.application.auth.logout import Logout
    from app.application.auth.setup_directory import RegisterSetupDirectory
    from app.application.auth.setup_first_admin import SetupFirstAdmin
    from app.application.directory.get_settings import GetDirectorySettings
    from app.application.directory.test_settings import TestDirectorySettings
    from app.application.directory.update_settings import UpdateDirectorySettings
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.user.delete_user import DeleteUser
    from app.application.user.list_users import ListUsers
    from app.application.user.register_user import RegisterUser
    from app.config.base import Settings


class Container:
    def __init__(
        self, settings: Settings, *, directory: DirectoryAuthenticator | None = None
    ) -> None:
        self._engine: AsyncEngine = create_async_engine(
            str(settings.database_url),
            pool_size=settings.db_pool_size,
            echo=settings.db_echo,
            pool_pre_ping=True,
        )
        sessions = async_sessionmaker(self._engine, expire_on_commit=False)
        self._uow = sql_unit_of_work_factory(sessions)
        self._clock = SystemClock()
        self.directory: DirectoryAuthenticator = directory or LdapDirectoryAuthenticator()
        self._auth = AuthAssembly(settings, self._uow, self._clock, self.directory)
        self._admin = AdminAssembly(
            self._uow,
            self._clock,
            self._auth.deps,
            allow_dev_sessions=self._auth.allow_dev_sessions,
        )

    async def check_ready(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("select 1"))

    async def dispose(self) -> None:
        await self._engine.dispose()

    def auth_status(self) -> GetAuthStatus:
        return self._auth.auth_status()

    def register_setup_directory(self) -> RegisterSetupDirectory:
        return self._auth.register_setup_directory()

    def setup_first_admin(self) -> SetupFirstAdmin:
        return self._auth.setup_first_admin()

    def directory_login(self) -> DirectoryLogin:
        return self._auth.directory_login()

    def dev_login(self) -> DevLogin:
        return self._auth.dev_login()

    def authenticate(self) -> Authenticate:
        return self._auth.authenticate()

    def logout(self) -> Logout:
        return self._auth.logout()

    def list_users(self) -> ListUsers:
        return self._admin.list_users()

    def register_user(self) -> RegisterUser:
        return self._admin.register_user()

    def delete_user(self) -> DeleteUser:
        return self._admin.delete_user()

    def get_directory_settings(self) -> GetDirectorySettings:
        return self._admin.get_directory_settings()

    def test_directory_settings(self) -> TestDirectorySettings:
        return self._admin.test_directory_settings()

    def update_directory_settings(self) -> UpdateDirectorySettings:
        return self._admin.update_directory_settings()

    def register_customer(self) -> RegisterCustomer:
        return RegisterCustomer(self._uow, self._clock)

    def get_customer(self) -> GetCustomer:
        return GetCustomer(self._uow)

    def list_customers(self) -> ListCustomers:
        return ListCustomers(self._uow)

    def update_customer(self) -> UpdateCustomer:
        return UpdateCustomer(self._uow, self._clock)

    def delete_customer(self) -> DeleteCustomer:
        return DeleteCustomer(self._uow, self._clock)

    def register_partner(self) -> RegisterPartner:
        return RegisterPartner(self._uow, self._clock)

    def get_partner(self) -> GetPartner:
        return GetPartner(self._uow)

    def list_partners(self) -> ListPartners:
        return ListPartners(self._uow)

    def update_partner(self) -> UpdatePartner:
        return UpdatePartner(self._uow, self._clock)

    def delete_partner(self) -> DeletePartner:
        return DeletePartner(self._uow, self._clock)

    def register_deal(self) -> RegisterDeal:
        return RegisterDeal(self._uow, self._clock)

    def get_deal(self) -> GetDeal:
        return GetDeal(self._uow)

    def get_deal_by_code(self) -> GetDealByCode:
        return GetDealByCode(self._uow)

    def list_deals(self) -> ListDeals:
        return ListDeals(self._uow)

    def update_deal(self) -> UpdateDeal:
        return UpdateDeal(self._uow, self._clock)

    def delete_deal(self) -> DeleteDeal:
        return DeleteDeal(self._uow, self._clock)

    def change_deal_stage(self) -> ChangeDealStage:
        return ChangeDealStage(self._uow, self._clock)

    def list_deal_stage_changes(self) -> ListDealStageChanges:
        return ListDealStageChanges(self._uow)

    def get_deal_pipeline(self) -> GetDealPipeline:
        return GetDealPipeline(self._uow)

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._uow, self._clock)

    def get_deal_action(self) -> GetDealAction:
        return GetDealAction(self._uow)

    def search_deal_actions(self) -> SearchDealActions:
        return SearchDealActions(self._uow)

    def update_deal_action(self) -> UpdateDealAction:
        return UpdateDealAction(self._uow, self._clock)

    def delete_deal_action(self) -> DeleteDealAction:
        return DeleteDealAction(self._uow, self._clock)
