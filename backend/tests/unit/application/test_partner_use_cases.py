from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.partner.delete_partner import DeletePartner
from app.application.partner.get_partner import GetPartner
from app.application.partner.list_partners import ListPartners
from app.application.partner.register_partner import RegisterPartner
from app.application.partner.update_partner import UpdatePartner
from app.application.ports.partner_repository import PartnerQuery
from app.domain.common.errors import InvalidValueError
from app.domain.partner.errors import PartnerNotFoundError
from app.domain.partner.value_objects import PartnerId
from tests.factories import make_partner_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


def _random_partner_id() -> PartnerId:
    return PartnerId(uuid4())


async def test_register_persists_the_partner_and_commits_once(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    partner = await RegisterPartner(uow_factory, clock).execute(make_partner_input())

    assert uow.commits == 1
    assert (await uow.partners.get(partner.id)).details.company_name == "한빛파트너스"
    assert partner.created_at == clock.now()


async def test_register_with_invalid_input_stores_nothing(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(InvalidValueError):
        await RegisterPartner(uow_factory, clock).execute(make_partner_input(phone="abc"))

    assert uow.commits == 0
    assert list(await uow.partners.list()) == []


async def test_get_returns_the_partner_and_missing_raises_not_found(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    registered = await RegisterPartner(uow_factory, clock).execute(make_partner_input())

    assert await GetPartner(uow_factory).execute(registered.id) == registered
    assert uow.commits == 1
    with pytest.raises(PartnerNotFoundError):
        await GetPartner(uow_factory).execute(_random_partner_id())


async def test_list_pages_in_creation_order_and_excludes_deleted(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    register = RegisterPartner(uow_factory, clock)
    created = []
    for number in range(4):
        clock.advance()
        created.append(await register.execute(make_partner_input(company_name=f"파트너{number}")))
    await DeletePartner(uow_factory, clock).execute(created[0].id)

    page = await ListPartners(uow_factory).execute(PartnerQuery(offset=1, limit=2))

    assert [p.id for p in page] == [created[2].id, created[3].id]


async def test_update_replaces_details_and_uses_the_clock(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    registered = await RegisterPartner(uow_factory, clock).execute(make_partner_input())
    clock.advance(300)

    updated = await UpdatePartner(uow_factory, clock).execute(
        registered.id, make_partner_input(company_name="새 파트너", email=None)
    )

    stored = await uow.partners.get(registered.id)
    assert stored.details.company_name == "새 파트너"
    assert stored.details.email is None
    assert updated.updated_at == clock.now()
    assert uow.commits == 2


async def test_update_missing_partner_raises_not_found(
    uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    with pytest.raises(PartnerNotFoundError):
        await UpdatePartner(uow_factory, clock).execute(_random_partner_id(), make_partner_input())


async def test_delete_removes_the_partner_physically(
    uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    registered = await RegisterPartner(uow_factory, clock).execute(make_partner_input())
    clock.advance(120)

    await DeletePartner(uow_factory, clock).execute(registered.id)

    with pytest.raises(PartnerNotFoundError):
        await GetPartner(uow_factory).execute(registered.id)
    with pytest.raises(PartnerNotFoundError):
        await uow.partners.get(registered.id)
    with pytest.raises(PartnerNotFoundError):
        await DeletePartner(uow_factory, clock).execute(registered.id)
