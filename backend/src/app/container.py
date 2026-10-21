"""Composition Root: Port와 구현체를 연결하고 유스케이스를 만들어 준다(UseCaseProvider 구현)."""

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.application.alert.get_alert_settings import GetAlertSettings
from app.application.alert.update_alert_settings import UpdateAlertSettings
from app.application.contact.delete_contact import DeleteContact
from app.application.contact.list_companies import ListContactCompanies
from app.application.contact.list_of_company import ListContactsOfCompany
from app.application.contact.register_contact import RegisterContact
from app.application.contact.search_contacts import SearchContacts
from app.application.contact.update_contact import UpdateContact
from app.application.deal.apply_change import ApplyDealChange
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.deletion_impact import GetDealDeletionImpact
from app.application.deal.get_deal import GetDeal
from app.application.deal.list_deal_history import ListDealHistory
from app.application.deal.list_deals import ListDeals
from app.application.deal.register_deal import RegisterDeal
from app.application.deal.update_deal import UpdateDeal
from app.application.deal.updated_periods import ListUpdatedPeriods
from app.application.deal_action.change_next_action_status import ChangeNextActionStatus
from app.application.deal_action.delete_deal_action import DeleteDealAction
from app.application.deal_action.get_deal_action import GetDealAction
from app.application.deal_action.list_deal_actions import ListDealActions
from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.deal_action.update_deal_action import UpdateDealAction
from app.container_action_type import ActionTypeUseCases
from app.container_admin import AdminAssembly
from app.container_auth import AuthAssembly
from app.container_catalog import CatalogAssembly
from app.container_forecast import ForecastUseCases
from app.container_storage import StorageAssembly
from app.container_vendor import VendorUseCases
from app.infra.auth.ldap import LdapDirectoryAuthenticator
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from app.infra.deal_code_source import RandomDealCodeSuffixSource
from app.infra.system_clock import SystemClock

if TYPE_CHECKING:
    from app.application.attachment.delete_attachment import DeleteAttachment
    from app.application.attachment.download_attachment import DownloadAttachment
    from app.application.attachment.get_attachment import GetAttachment
    from app.application.attachment.list_attachments import ListAttachments
    from app.application.attachment.upload_attachment import UploadAttachment
    from app.application.auth.auth_status import GetAuthStatus
    from app.application.auth.authenticate import Authenticate
    from app.application.auth.dev_login import DevLogin
    from app.application.auth.directory_login import DirectoryLogin
    from app.application.auth.logout import Logout
    from app.application.auth.setup_directory import RegisterSetupDirectory
    from app.application.auth.setup_first_admin import SetupFirstAdmin
    from app.application.auth.setup_storage import RegisterSetupStorage
    from app.application.auth.setup_storage import TestSetupStorage as ProbeSetupStorage
    from app.application.bant.delete_label import DeleteBantLabel
    from app.application.bant.list_labels import ListBantLabels
    from app.application.bant.register_label import RegisterBantLabel
    from app.application.bant.rename_label import RenameBantLabel
    from app.application.code.delete_code import DeleteCode
    from app.application.code.list_code_set import ListCodeSet
    from app.application.code.list_codes_with_usage import ListCodesWithUsage
    from app.application.code.register_code import RegisterCode
    from app.application.code.rename_code import RenameCode
    from app.application.code.reorder_codes import ReorderCodes
    from app.application.directory.get_settings import GetDirectorySettings
    from app.application.directory.test_settings import TestDirectorySettings
    from app.application.directory.update_settings import UpdateDirectorySettings
    from app.application.ports.clock import Clock
    from app.application.ports.directory import DirectoryAuthenticator
    from app.application.storage.get_settings import GetStorageSettings
    from app.application.storage.test_settings import TestStorageSettings as ProbeStorageSettings
    from app.application.storage.update_settings import UpdateStorageSettings
    from app.application.user.delete_user import DeleteUser
    from app.application.user.list_user_options import ListUserOptions
    from app.application.user.list_users import ListUsers
    from app.application.user.register_user import RegisterUser
    from app.application.user.resolve_user_refs import ResolveUserRefs
    from app.config.base import Settings


class Container(VendorUseCases, ActionTypeUseCases, ForecastUseCases):
    def __init__(
        self,
        settings: Settings,
        *,
        directory: DirectoryAuthenticator | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._engine: AsyncEngine = create_async_engine(
            str(settings.database_url),
            pool_size=settings.db_pool_size,
            echo=settings.db_echo,
            pool_pre_ping=True,
        )
        sessions = async_sessionmaker(self._engine, expire_on_commit=False)
        self._uow = sql_unit_of_work_factory(sessions)
        self._clock: Clock = clock or SystemClock()
        self._suffix_source = RandomDealCodeSuffixSource()
        self.directory: DirectoryAuthenticator = directory or LdapDirectoryAuthenticator()
        self._auth = AuthAssembly(settings, self._uow, self._clock, self.directory)
        self._catalog = CatalogAssembly(self._uow, self._clock)
        self._storage = StorageAssembly(self._uow, self._clock)
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

    def register_setup_storage(self) -> RegisterSetupStorage:
        return self._storage.register_setup_storage()

    def test_setup_storage(self) -> ProbeSetupStorage:
        return self._storage.test_setup_storage()

    def get_alert_settings(self) -> GetAlertSettings:
        return GetAlertSettings(self._uow)

    def update_alert_settings(self) -> UpdateAlertSettings:
        return UpdateAlertSettings(self._uow, self._clock)

    def get_storage_settings(self) -> GetStorageSettings:
        return self._storage.get_storage_settings()

    def update_storage_settings(self) -> UpdateStorageSettings:
        return self._storage.update_storage_settings()

    def test_storage_settings(self) -> ProbeStorageSettings:
        return self._storage.test_storage_settings()

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

    def list_user_options(self) -> ListUserOptions:
        return self._admin.list_user_options()

    def resolve_user_refs(self) -> ResolveUserRefs:
        return self._admin.resolve_user_refs()

    def get_directory_settings(self) -> GetDirectorySettings:
        return self._admin.get_directory_settings()

    def test_directory_settings(self) -> TestDirectorySettings:
        return self._admin.test_directory_settings()

    def update_directory_settings(self) -> UpdateDirectorySettings:
        return self._admin.update_directory_settings()

    def search_contacts(self) -> SearchContacts:
        return SearchContacts(self._uow)

    def list_contact_companies(self) -> ListContactCompanies:
        return ListContactCompanies(self._uow)

    def list_contacts_of_company(self) -> ListContactsOfCompany:
        return ListContactsOfCompany(self._uow)

    def register_contact(self) -> RegisterContact:
        return RegisterContact(self._uow, self._clock)

    def update_contact(self) -> UpdateContact:
        return UpdateContact(self._uow, self._clock)

    def delete_contact(self) -> DeleteContact:
        return DeleteContact(self._uow)

    def register_deal(self) -> RegisterDeal:
        return RegisterDeal(self._uow, self._clock, self._suffix_source)

    def get_deal(self) -> GetDeal:
        return GetDeal(self._uow, self._clock)

    def list_deals(self) -> ListDeals:
        return ListDeals(self._uow, self._clock)

    def list_updated_periods(self) -> ListUpdatedPeriods:
        return ListUpdatedPeriods(self._clock)

    def list_deal_history(self) -> ListDealHistory:
        return ListDealHistory(self._uow)

    def apply_deal_change(self) -> ApplyDealChange:
        return ApplyDealChange(self._uow, self._clock)

    def get_deal_deletion_impact(self) -> GetDealDeletionImpact:
        return GetDealDeletionImpact(self._uow)

    def update_deal(self) -> UpdateDeal:
        return UpdateDeal(self._uow, self._clock)

    def delete_deal(self) -> DeleteDeal:
        return DeleteDeal(self._uow, self._clock, self._storage.file_storage)

    def list_attachments(self) -> ListAttachments:
        return self._storage.list_attachments()

    def get_attachment(self) -> GetAttachment:
        return self._storage.get_attachment()

    def upload_attachment(self) -> UploadAttachment:
        return self._storage.upload_attachment()

    def delete_attachment(self) -> DeleteAttachment:
        return self._storage.delete_attachment()

    def download_attachment(self) -> DownloadAttachment:
        return self._storage.download_attachment()

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._uow, self._clock)

    def get_deal_action(self) -> GetDealAction:
        return GetDealAction(self._uow)

    def list_deal_actions(self) -> ListDealActions:
        return ListDealActions(self._uow)

    def update_deal_action(self) -> UpdateDealAction:
        return UpdateDealAction(self._uow, self._clock)

    def change_next_action_status(self) -> ChangeNextActionStatus:
        return ChangeNextActionStatus(self._uow, self._clock)

    def delete_deal_action(self) -> DeleteDealAction:
        return DeleteDealAction(self._uow, self._clock)

    def list_code_set(self) -> ListCodeSet:
        return self._catalog.list_code_set()

    def list_codes_with_usage(self) -> ListCodesWithUsage:
        return self._catalog.list_codes_with_usage()

    def register_code(self) -> RegisterCode:
        return self._catalog.register_code()

    def rename_code(self) -> RenameCode:
        return self._catalog.rename_code()

    def reorder_codes(self) -> ReorderCodes:
        return self._catalog.reorder_codes()

    def delete_code(self) -> DeleteCode:
        return self._catalog.delete_code()

    def list_bant_labels(self) -> ListBantLabels:
        return self._catalog.list_bant_labels()

    def register_bant_label(self) -> RegisterBantLabel:
        return self._catalog.register_bant_label()

    def rename_bant_label(self) -> RenameBantLabel:
        return self._catalog.rename_bant_label()

    def delete_bant_label(self) -> DeleteBantLabel:
        return self._catalog.delete_bant_label()
