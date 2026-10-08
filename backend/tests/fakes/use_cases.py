"""UseCaseProvider의 Fake. 실제 유스케이스를 FakeUnitOfWork·FixedClock으로 조립한다(DB 없음)."""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.auth.authenticate import Authenticate
from app.application.auth.begin_login import BeginLogin
from app.application.auth.complete_login import CompleteLogin
from app.application.auth.dev_login import DevLogin
from app.application.auth.issue_session import IssueSession
from app.application.auth.login_state import LoginStateCodec
from app.application.auth.logout import Logout
from app.application.auth.role_mapping import RoleMapper
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
from tests.factories import NOW
from tests.fakes.identity_provider import FakeIdentityProvider
from tests.fakes.unit_of_work import FakeUnitOfWork, SteppingClock

if TYPE_CHECKING:
    from app.domain.auth.principal import Principal


class FakeUseCases:
    def __init__(self) -> None:
        self.uow = FakeUnitOfWork()
        self.clock = SteppingClock(NOW)
        self.ready_error: Exception | None = None
        self.identity_provider = FakeIdentityProvider()
        self._login_state = LoginStateCodec("s" * 40, self.clock)
        self._roles = RoleMapper(["Sales-Admins"], ["Sales-Team"])
        self._issue_session = IssueSession(self._factory, self.clock, timedelta(hours=8))

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

    def begin_login(self) -> BeginLogin:
        return BeginLogin(self.identity_provider, self._login_state)

    def complete_login(self) -> CompleteLogin:
        return CompleteLogin(
            self.identity_provider, self._login_state, self._roles, self._issue_session
        )

    def dev_login(self) -> DevLogin:
        return DevLogin(self._issue_session)

    def authenticate(self) -> Authenticate:
        return Authenticate(self._factory, self.clock)

    def logout(self) -> Logout:
        return Logout(self._factory, self.clock)

    async def login_as(self, principal: Principal) -> str:
        """임의 사용자(subject)의 세션을 발급하고 쿠키에 넣을 토큰을 돌려준다(다중 사용자 E2E용)."""
        return (await self._issue_session.execute(principal)).token

    async def check_ready(self) -> None:
        if self.ready_error is not None:
            raise self.ready_error
