"""UseCaseProvider의 Fake. 실제 유스케이스를 FakeUnitOfWork·FixedClock으로 조립한다(DB 없음)."""

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.get_customer import GetCustomer
from app.application.customer.list_customers import ListCustomers
from app.application.customer.register_customer import RegisterCustomer
from app.application.customer.update_customer import UpdateCustomer
from app.application.deal.delete_deal import DeleteDeal
from app.application.deal.get_deal import GetDeal
from app.application.deal.get_deal_by_code import GetDealByCode
from app.application.deal.list_deals import ListDeals
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
from tests.fakes.unit_of_work import FakeUnitOfWork, SteppingClock


class FakeUseCases:
    def __init__(self) -> None:
        self.uow = FakeUnitOfWork()
        self.clock = SteppingClock(NOW)
        self.ready_error: Exception | None = None

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

    async def check_ready(self) -> None:
        if self.ready_error is not None:
            raise self.ready_error
