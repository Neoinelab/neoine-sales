"""고객·파트너 삭제와 Deal 등록이 겹쳐도 500이 아닌 도메인 오류가 되고 고아 행이 없다(AC7).

가드(exists_for_*)와 존재 검사(ensure_references_exist) 뒤에 반대쪽이 끼어드는 경쟁은
FK(RESTRICT)가 최종 방어선이고, 저장소가 그 위반을 같은 도메인 오류로 변환한다.
"""

import asyncio
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.application.customer.delete_customer import DeleteCustomer
from app.application.deal.register_deal import RegisterDeal
from app.application.partner.delete_partner import DeletePartner
from app.domain.common.errors import InvalidReferenceError
from app.domain.customer.errors import CustomerInUseError, CustomerNotFoundError
from app.domain.partner.errors import PartnerInUseError, PartnerNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import later, make_customer, make_deal_input, make_partner
from tests.fakes.unit_of_work import FixedClock
from tests.support.gated_uow import gated

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Any

    from sqlalchemy.engine import URL

    from app.application.deal.inputs import DealInput
    from app.application.ports.unit_of_work import UnitOfWorkFactory

pytestmark = pytest.mark.integration

KINDS = ["customer", "partner"]


@pytest_asyncio.fixture
async def uow_factory(test_database_url: URL) -> AsyncIterator[UnitOfWorkFactory]:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "truncate deal_actions, deal_stage_changes, deals, customers, partners cascade"
                )
            )
    finally:
        await engine.dispose()


class _Fixture:
    def __init__(self, uow_factory: UnitOfWorkFactory, kind: str) -> None:
        self.uow_factory = uow_factory
        self.kind = kind
        self.customer = make_customer()
        self.partner = make_partner()

    async def seed(self) -> None:
        async with self.uow_factory() as uow:
            await uow.customers.add(self.customer)
            await uow.partners.add(self.partner)
            await uow.commit()

    @property
    def target_id(self) -> Any:  # noqa: ANN401
        return self.customer.id if self.kind == "customer" else self.partner.id

    @property
    def in_use(self) -> type[Exception]:
        return CustomerInUseError if self.kind == "customer" else PartnerInUseError

    @property
    def not_found(self) -> type[Exception]:
        return CustomerNotFoundError if self.kind == "customer" else PartnerNotFoundError

    def delete_use_case(self, factory: UnitOfWorkFactory) -> DeleteCustomer | DeletePartner:
        clock = FixedClock(later(60))
        return (
            DeleteCustomer(factory, clock)
            if self.kind == "customer"
            else DeletePartner(factory, clock)
        )

    def register_use_case(self, factory: UnitOfWorkFactory) -> RegisterDeal:
        return RegisterDeal(factory, FixedClock(later(61)))

    def deal_input(self) -> DealInput:
        return make_deal_input(self.customer.id, partner_id=self.partner.id)

    async def counts(self) -> tuple[int, int]:
        """(고객 또는 파트너 행 수, Deal 수)."""
        async with self.uow_factory() as uow:
            deals = len(await uow.deals.list())
            if self.kind == "customer":
                return len(await uow.customers.list()), deals
            return len(await uow.partners.list()), deals


@pytest.fixture(params=KINDS)
async def race(request: pytest.FixtureRequest, uow_factory: UnitOfWorkFactory) -> _Fixture:
    fixture = _Fixture(uow_factory, request.param)
    await fixture.seed()
    return fixture


async def test_deal_registered_after_the_delete_guard_turns_the_delete_into_in_use(
    race: _Fixture,
) -> None:
    """가드를 통과한 삭제가 멈춘 사이 Deal이 커밋되면 FK 위반이 InUse가 된다."""
    reached, release = asyncio.Event(), asyncio.Event()
    gated_factory = gated(
        race.uow_factory,
        attribute=f"{race.kind}s",
        method="delete",
        reached=reached,
        release=release,
    )
    delete = asyncio.create_task(race.delete_use_case(gated_factory).execute(race.target_id))
    await asyncio.wait_for(reached.wait(), timeout=10)
    await race.register_use_case(race.uow_factory).execute(race.deal_input())
    release.set()

    with pytest.raises(race.in_use):
        await asyncio.wait_for(delete, timeout=15)

    assert await race.counts() == (1, 1)


async def test_deal_registered_while_the_contact_is_deleted_fails_as_an_invalid_reference(
    race: _Fixture,
) -> None:
    """존재 검사를 통과한 Deal 등록이 멈춘 사이 대상이 삭제되면 InvalidReferenceError."""
    reached, release = asyncio.Event(), asyncio.Event()
    gated_factory = gated(
        race.uow_factory, attribute="deals", method="add", reached=reached, release=release
    )
    register = asyncio.create_task(race.register_use_case(gated_factory).execute(race.deal_input()))
    await asyncio.wait_for(reached.wait(), timeout=10)
    await race.delete_use_case(race.uow_factory).execute(race.target_id)
    release.set()

    with pytest.raises(InvalidReferenceError):
        await asyncio.wait_for(register, timeout=15)

    assert await race.counts() == (0, 0)
