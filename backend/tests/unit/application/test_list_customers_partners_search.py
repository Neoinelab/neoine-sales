"""ListCustomers / ListPartners: Query를 받아 키워드·페이지를 적용한다(Fake UoW). C-1·C-2·C-3."""

from typing import TYPE_CHECKING

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.list_customers import ListCustomers
from app.application.customer.register_customer import RegisterCustomer
from app.application.partner.delete_partner import DeletePartner
from app.application.partner.list_partners import ListPartners
from app.application.partner.register_partner import RegisterPartner
from app.application.ports.customer_repository import CustomerQuery
from app.application.ports.partner_repository import PartnerQuery
from tests.factories import make_customer_input, make_partner_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FixedClock


async def test_list_customers_filters_by_keyword_and_excludes_deleted(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterCustomer(uow_factory, clock)
    names = ("Alpha 상사", "베타", "ALPHA 둘째", "alpha 삭제")
    created = []
    for name in names:
        clock.advance()
        created.append(await register.execute(make_customer_input(company_name=name)))
    await DeleteCustomer(uow_factory, clock).execute(created[3].id)

    found = await ListCustomers(uow_factory).execute(CustomerQuery(keyword="alpha"))

    assert [c.id for c in found] == [created[0].id, created[2].id]


async def test_list_customers_pages_after_filtering(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterCustomer(uow_factory, clock)
    created = []
    for n in range(4):
        clock.advance()
        created.append(await register.execute(make_customer_input(company_name=f"Hit{n}")))

    found = await ListCustomers(uow_factory).execute(
        CustomerQuery(keyword="hit", offset=1, limit=2)
    )

    assert [c.id for c in found] == [created[1].id, created[2].id]


async def test_list_partners_filters_by_keyword_and_excludes_deleted(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterPartner(uow_factory, clock)
    created = []
    for name in ("Alpha 파트너", "베타", "alpha 삭제"):
        clock.advance()
        created.append(await register.execute(make_partner_input(company_name=name)))
    await DeletePartner(uow_factory, clock).execute(created[2].id)

    found = await ListPartners(uow_factory).execute(PartnerQuery(keyword="ALPHA"))

    assert [p.id for p in found] == [created[0].id]


async def test_list_partners_pages_after_filtering(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterPartner(uow_factory, clock)
    created = []
    for n in range(4):
        clock.advance()
        created.append(await register.execute(make_partner_input(company_name=f"Hit{n}")))

    found = await ListPartners(uow_factory).execute(PartnerQuery(keyword="hit", offset=2, limit=5))

    assert [p.id for p in found] == [created[2].id, created[3].id]
