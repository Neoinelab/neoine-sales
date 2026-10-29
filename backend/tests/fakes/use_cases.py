"""UseCaseProvider의 Fake. 실제 유스케이스를 FakeUnitOfWork·FixedClock으로 조립한다(DB 없음)."""

from dataclasses import replace
from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import make_directory_settings, make_user
from tests.fakes.attachment_use_cases import AttachmentUseCases
from tests.fakes.catalog_use_cases import CatalogUseCases
from tests.fakes.contact_use_cases import ContactUseCases
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.fakes.deal_use_cases import DealUseCases
from tests.fakes.file_storage import FakeFileStorage
from tests.fakes.partner_meeting_use_cases import PartnerMeetingUseCases
from tests.fakes.unit_of_work import FakeUnitOfWork, SteppingClock

if TYPE_CHECKING:
    from app.application.alert.get_alert_settings import GetAlertSettings
    from app.application.alert.update_alert_settings import UpdateAlertSettings
    from app.application.auth.auth_status import GetAuthStatus
    from app.application.auth.authenticate import Authenticate
    from app.application.auth.dev_login import DevLogin
    from app.application.auth.directory_login import DirectoryLogin
    from app.application.auth.logout import Logout
    from app.application.auth.setup_directory import RegisterSetupDirectory
    from app.application.auth.setup_first_admin import SetupFirstAdmin
    from app.application.auth.setup_storage import RegisterSetupStorage, TestSetupStorage
    from app.application.dashboard.get_summary import GetDashboardSummary
    from app.application.deal_action.change_next_action_status import ChangeNextActionStatus
    from app.application.deal_action.delete_deal_action import DeleteDealAction
    from app.application.deal_action.get_deal_action import GetDealAction
    from app.application.deal_action.list_deal_actions import ListDealActions
    from app.application.deal_action.register_deal_action import RegisterDealAction
    from app.application.deal_action.update_deal_action import UpdateDealAction
    from app.application.directory.get_settings import GetDirectorySettings
    from app.application.directory.test_settings import TestDirectorySettings
    from app.application.directory.update_settings import UpdateDirectorySettings
    from app.application.forecast.get_snapshot_summary import GetForecastSnapshotSummary
    from app.application.forecast.get_summary import GetForecastSummary
    from app.application.forecast.list_snapshots import ListForecastSnapshots
    from app.application.forecast.take_snapshot import TakeForecastSnapshot
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.application.report.change_report_layout import ChangeReportLayout
    from app.application.report.copy_report import CopyReport
    from app.application.report.create_report import CreateReport
    from app.application.report.delete_report import DeleteReport
    from app.application.report.get_report import GetReport
    from app.application.report.list_fields import ListReportFields
    from app.application.report.list_reports import ListReports
    from app.application.report.run_report import RunReport
    from app.application.report.run_saved_report import RunSavedReport
    from app.application.report.update_report import UpdateReport
    from app.application.storage.get_settings import GetStorageSettings
    from app.application.storage.test_settings import TestStorageSettings
    from app.application.storage.update_settings import UpdateStorageSettings
    from app.application.time.get_server_time import GetServerTime
    from app.application.user.change_user_role import ChangeUserRole
    from app.application.user.delete_user import DeleteUser
    from app.application.user.list_user_options import ListUserOptions
    from app.application.user.list_users import ListUsers
    from app.application.user.register_user import RegisterUser
    from app.application.user.resolve_user_refs import ResolveUserRefs
    from app.domain.auth.principal import Principal
    from app.domain.directory.settings import DirectorySettings
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId
    from tests.fakes.auth_stack import AuthStack
    from tests.fakes.directory import FakeDirectoryAuthenticator


class FakeUseCases(
    CatalogUseCases, ContactUseCases, DealUseCases, AttachmentUseCases, PartnerMeetingUseCases
):
    def __init__(self, *, allow_dev_sessions: bool = True) -> None:
        self.uow = FakeUnitOfWork()
        self.clock = SteppingClock(NOW)
        self.suffix_source = FakeDealCodeSuffixSource()
        self.ready_error: Exception | None = None
        self.file_storage = FakeFileStorage()
        # 인증 모듈이 없으면 인증과 무관한 테스트의 수집까지 막히므로 사용 시점에 가져온다
        from tests.fakes.auth_stack import build_auth_stack  # noqa: PLC0415

        self._auth: AuthStack = build_auth_stack(
            self._factory, self.clock, allow_dev_sessions=allow_dev_sessions
        )
        self.directory: FakeDirectoryAuthenticator = self._auth.directory
        from tests.fakes.admin_stack import build_admin_stack  # noqa: PLC0415

        self._admin = build_admin_stack(
            self._auth, self._factory, self.clock, allow_dev_sessions=allow_dev_sessions
        )

    def _factory(self) -> FakeUnitOfWork:
        return self.uow

    def _contact_uow_factory(self) -> UnitOfWorkFactory:
        return self._factory

    def _deal_uow_factory(self) -> UnitOfWorkFactory:
        return self._factory

    def _attachment_uow_factory(self) -> UnitOfWorkFactory:
        return self._factory

    def _meeting_uow_factory(self) -> UnitOfWorkFactory:
        return self._factory

    # Action 유스케이스는 사용 시점에 가져온다(P2 R1: 구현 전에도 이 Fake를 쓰는 테스트가 수집된다)
    def register_deal_action(self) -> RegisterDealAction:
        from app.application.deal_action.register_deal_action import (  # noqa: PLC0415
            RegisterDealAction,
        )

        return RegisterDealAction(self._factory, self.clock)

    def get_deal_action(self) -> GetDealAction:
        from app.application.deal_action.get_deal_action import GetDealAction  # noqa: PLC0415

        return GetDealAction(self._factory)

    def list_deal_actions(self) -> ListDealActions:
        from app.application.deal_action.list_deal_actions import ListDealActions  # noqa: PLC0415

        return ListDealActions(self._factory)

    def update_deal_action(self) -> UpdateDealAction:
        from app.application.deal_action.update_deal_action import (  # noqa: PLC0415
            UpdateDealAction,
        )

        return UpdateDealAction(self._factory, self.clock)

    def change_next_action_status(self) -> ChangeNextActionStatus:
        from app.application.deal_action.change_next_action_status import (  # noqa: PLC0415
            ChangeNextActionStatus,
        )

        return ChangeNextActionStatus(self._factory, self.clock)

    def delete_deal_action(self) -> DeleteDealAction:
        from app.application.deal_action.delete_deal_action import (  # noqa: PLC0415
            DeleteDealAction,
        )

        return DeleteDealAction(self._factory, self.clock)

    # 저장 위치 유스케이스도 사용 시점에 가져온다(P2b R1: 구현 전에도 수집된다)
    def register_setup_storage(self) -> RegisterSetupStorage:
        from app.application.auth.setup_storage import RegisterSetupStorage  # noqa: PLC0415

        return RegisterSetupStorage(self._factory, self.clock, self.file_storage)

    def test_setup_storage(self) -> TestSetupStorage:
        from app.application.auth.setup_storage import TestSetupStorage  # noqa: PLC0415

        return TestSetupStorage(self._factory, self.file_storage)

    def get_storage_settings(self) -> GetStorageSettings:
        from app.application.storage.get_settings import GetStorageSettings  # noqa: PLC0415

        return GetStorageSettings(self._factory)

    def update_storage_settings(self) -> UpdateStorageSettings:
        from app.application.storage.update_settings import (  # noqa: PLC0415
            UpdateStorageSettings,
        )

        return UpdateStorageSettings(self._factory, self.clock, self.file_storage)

    def test_storage_settings(self) -> TestStorageSettings:
        from app.application.storage.test_settings import TestStorageSettings  # noqa: PLC0415

        return TestStorageSettings(self.file_storage)

    # 경고 기준 유스케이스도 사용 시점에 가져온다(P3 R1: 구현 전에도 수집된다)
    def get_alert_settings(self) -> GetAlertSettings:
        from app.application.alert.get_alert_settings import GetAlertSettings  # noqa: PLC0415

        return GetAlertSettings(self._factory)

    def update_alert_settings(self) -> UpdateAlertSettings:
        from app.application.alert.update_alert_settings import (  # noqa: PLC0415
            UpdateAlertSettings,
        )

        return UpdateAlertSettings(self._factory, self.clock)

    # Forecast 요약 유스케이스도 사용 시점에 가져온다(P6 R1: 구현 전에도 수집된다)
    def get_forecast_summary(self) -> GetForecastSummary:
        from app.application.forecast.get_summary import GetForecastSummary  # noqa: PLC0415

        return GetForecastSummary(self._factory, self.clock)

    # Dashboard 요약 유스케이스도 사용 시점에 가져온다(구현 전에도 수집된다)
    def get_dashboard_summary(self) -> GetDashboardSummary:
        from app.application.dashboard.get_summary import GetDashboardSummary  # noqa: PLC0415

        return GetDashboardSummary(self._factory, self.clock)

    # Reports 유스케이스도 사용 시점에 가져온다(구현 전에도 수집된다)
    def list_report_fields(self) -> ListReportFields:
        from app.application.report.list_fields import ListReportFields  # noqa: PLC0415

        return ListReportFields()

    def run_report(self) -> RunReport:
        from app.application.report.run_report import RunReport  # noqa: PLC0415

        return RunReport(self._factory, self.clock)

    # 저장 리포트 유스케이스(Reports 3단계)도 사용 시점에 가져온다(구현 전에도 수집된다)
    def list_reports(self) -> ListReports:
        from app.application.report.list_reports import ListReports  # noqa: PLC0415

        return ListReports(self._factory)

    def get_report(self) -> GetReport:
        from app.application.report.get_report import GetReport  # noqa: PLC0415

        return GetReport(self._factory)

    def create_report(self) -> CreateReport:
        from app.application.report.create_report import CreateReport  # noqa: PLC0415

        return CreateReport(self._factory, self.clock)

    def update_report(self) -> UpdateReport:
        from app.application.report.update_report import UpdateReport  # noqa: PLC0415

        return UpdateReport(self._factory, self.clock)

    def change_report_layout(self) -> ChangeReportLayout:
        from app.application.report.change_report_layout import (  # noqa: PLC0415
            ChangeReportLayout,
        )

        return ChangeReportLayout(self._factory, self.clock)

    def copy_report(self) -> CopyReport:
        from app.application.report.copy_report import CopyReport  # noqa: PLC0415

        return CopyReport(self._factory, self.clock)

    def delete_report(self) -> DeleteReport:
        from app.application.report.delete_report import DeleteReport  # noqa: PLC0415

        return DeleteReport(self._factory)

    def run_saved_report(self) -> RunSavedReport:
        from app.application.report.run_saved_report import RunSavedReport  # noqa: PLC0415

        return RunSavedReport(self._factory, self.clock)

    # 서버 시각 유스케이스도 사용 시점에 가져온다(구현 전에도 수집된다). DB를 쓰지 않는다
    def get_server_time(self) -> GetServerTime:
        from app.application.time.get_server_time import GetServerTime  # noqa: PLC0415

        return GetServerTime(self.clock)

    # 월말 스냅숏 유스케이스도 사용 시점에 가져온다(P6 R2: 구현 전에도 수집된다)
    def take_forecast_snapshot(self) -> TakeForecastSnapshot:
        from app.application.forecast.take_snapshot import TakeForecastSnapshot  # noqa: PLC0415

        return TakeForecastSnapshot(self._factory, self.clock)

    def list_forecast_snapshots(self) -> ListForecastSnapshots:
        from app.application.forecast.list_snapshots import ListForecastSnapshots  # noqa: PLC0415

        return ListForecastSnapshots(self._factory)

    def get_forecast_snapshot_summary(self) -> GetForecastSnapshotSummary:
        from app.application.forecast.get_snapshot_summary import (  # noqa: PLC0415
            GetForecastSnapshotSummary,
        )

        return GetForecastSnapshotSummary(self._factory)

    def auth_status(self) -> GetAuthStatus:
        return self._auth.status

    def register_setup_directory(self) -> RegisterSetupDirectory:
        return self._auth.register_directory

    def setup_first_admin(self) -> SetupFirstAdmin:
        return self._auth.setup_admin

    def directory_login(self) -> DirectoryLogin:
        return self._auth.login

    def dev_login(self) -> DevLogin:
        return self._auth.dev_login

    def authenticate(self) -> Authenticate:
        return self._auth.authenticate

    def logout(self) -> Logout:
        return self._auth.logout

    def list_users(self) -> ListUsers:
        return self._admin.list_users

    def register_user(self) -> RegisterUser:
        return self._admin.register_user

    def delete_user(self) -> DeleteUser:
        return self._admin.delete_user

    # 역할 변경 유스케이스도 사용 시점에 가져온다(구현 전에도 이 Fake를 쓰는 테스트가 수집된다)
    def change_user_role(self) -> ChangeUserRole:
        from app.application.user.change_user_role import ChangeUserRole  # noqa: PLC0415

        return ChangeUserRole(self._factory, self.clock)

    def list_user_options(self) -> ListUserOptions:
        return self._admin.list_user_options

    def resolve_user_refs(self) -> ResolveUserRefs:
        return self._admin.resolve_user_refs

    def get_directory_settings(self) -> GetDirectorySettings:
        return self._admin.get_settings

    def update_directory_settings(self) -> UpdateDirectorySettings:
        return self._admin.update_settings

    def test_directory_settings(self) -> TestDirectorySettings:
        return self._admin.test_settings

    async def seed_directory(self, settings: DirectorySettings | None = None) -> None:
        """AD 설정을 저장소에 직접 넣는다(1단계를 마친 상태). 유스케이스를 거치지 않는다."""
        async with self._factory() as uow:
            await uow.directory_settings.save(
                settings or make_directory_settings(),
                expected_revision=None,
                updated_by=None,
                now=self.clock.now(),
            )
            await uow.commit()

    async def seed_storage(self, path: str = "/data/neoine-sales/files") -> None:
        """파일 저장 위치를 저장소에 직접 넣는다(2단계를 마친 상태). 유스케이스를 거치지 않는다."""
        from app.domain.storage.path import StoragePath  # noqa: PLC0415

        async with self._factory() as uow:
            await uow.storage_settings.save(
                StoragePath.parse(path), updated_by=None, now=self.clock.now()
            )
            await uow.commit()

    async def seed_user(
        self, login_id: str, role: Role = Role.SALES, *, display_name: str | None = None
    ) -> User:
        user = make_user(login_id, role, now=self.clock.now())
        if display_name is not None:  # 로그인 때 AD에서 받은 표시 이름
            user.record_login(self.clock.now(), display_name=display_name, email=None)
        async with self._factory() as uow:
            await uow.users.add(user)
            await uow.commit()
        return user

    async def user_id_of(self, login_id: str) -> UserId:
        """재직 사용자의 id."""
        async with self._factory() as uow:
            user = await uow.users.get_active_by_login_id(LoginId(login_id))
        assert user is not None, login_id
        return user.id

    async def resign_user(self, user_id: UserId) -> None:
        """사용자를 퇴사 처리하고 세션 행을 지운다(DeleteUser의 소프트 분기 결과를 직접 만든다)."""
        async with self._factory() as uow:
            user = await uow.users.get(user_id)
            user.resign(self.clock.now())
            await uow.users.update(user)
            await uow.sessions.delete_all_for_user(user_id)
            await uow.commit()

    async def issue_session_for(self, principal: Principal) -> str:
        """users 행 확인 없이 세션만 발급한다(principal.user_id의 행이 이미 있어야 한다)."""
        return (await self._auth.issue.execute(principal)).token

    async def login_as(self, principal: Principal) -> str:
        """subject를 아이디로 한 재직 사용자 행을 (없을 때만) 등록하고 그 id로 세션을 발급한다."""
        async with self._factory() as uow:
            user = await uow.users.get_active_by_login_id(LoginId(principal.subject))
            if user is None:
                user = make_user(principal.subject, principal.role, now=self.clock.now())
                user.record_login(
                    self.clock.now(), display_name=principal.name, email=principal.email
                )
                await uow.users.add(user)
                await uow.commit()
        return (await self._auth.issue.execute(replace(principal, user_id=user.id))).token

    async def check_ready(self) -> None:
        if self.ready_error is not None:
            raise self.ready_error
