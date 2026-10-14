"""UseCaseProvider의 Fake. 실제 유스케이스를 FakeUnitOfWork·FixedClock으로 조립한다(DB 없음)."""

from dataclasses import replace
from typing import TYPE_CHECKING

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
from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.factories import NOW
from tests.factories_auth import make_directory_settings, make_user
from tests.fakes.unit_of_work import FakeUnitOfWork, SteppingClock

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


class FakeUseCases:
    def __init__(self, *, allow_dev_sessions: bool = True) -> None:
        self.uow = FakeUnitOfWork()
        self.clock = SteppingClock(NOW)
        self.ready_error: Exception | None = None
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

    def register_customer(self) -> RegisterCustomer:
        return RegisterCustomer(self._factory, self.clock)

    def get_customer(self) -> GetCustomer:
        return GetCustomer(self._factory)

    def list_customers(self) -> ListCustomers:
        return ListCustomers(self._factory)

    def update_customer(self) -> UpdateCustomer:
        return UpdateCustomer(self._factory, self.clock)

    def delete_customer(self) -> DeleteCustomer:
        return DeleteCustomer(self._factory, self.clock)

    def register_partner(self) -> RegisterPartner:
        return RegisterPartner(self._factory, self.clock)

    def get_partner(self) -> GetPartner:
        return GetPartner(self._factory)

    def list_partners(self) -> ListPartners:
        return ListPartners(self._factory)

    def update_partner(self) -> UpdatePartner:
        return UpdatePartner(self._factory, self.clock)

    def delete_partner(self) -> DeletePartner:
        return DeletePartner(self._factory, self.clock)

    def register_deal(self) -> RegisterDeal:
        return RegisterDeal(self._factory, self.clock)

    def get_deal(self) -> GetDeal:
        return GetDeal(self._factory)

    def get_deal_by_code(self) -> GetDealByCode:
        return GetDealByCode(self._factory)

    def list_deals(self) -> ListDeals:
        return ListDeals(self._factory)

    def update_deal(self) -> UpdateDeal:
        return UpdateDeal(self._factory, self.clock)

    def delete_deal(self) -> DeleteDeal:
        return DeleteDeal(self._factory, self.clock)

    def change_deal_stage(self) -> ChangeDealStage:
        return ChangeDealStage(self._factory, self.clock)

    def list_deal_stage_changes(self) -> ListDealStageChanges:
        return ListDealStageChanges(self._factory)

    def get_deal_pipeline(self) -> GetDealPipeline:
        return GetDealPipeline(self._factory)

    def register_deal_action(self) -> RegisterDealAction:
        return RegisterDealAction(self._factory, self.clock)

    def get_deal_action(self) -> GetDealAction:
        return GetDealAction(self._factory)

    def search_deal_actions(self) -> SearchDealActions:
        return SearchDealActions(self._factory)

    def update_deal_action(self) -> UpdateDealAction:
        return UpdateDealAction(self._factory, self.clock)

    def delete_deal_action(self) -> DeleteDealAction:
        return DeleteDealAction(self._factory, self.clock)

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
