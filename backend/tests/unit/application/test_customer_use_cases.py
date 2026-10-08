from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.customer.delete_customer import DeleteCustomer
from app.application.customer.get_customer import GetCustomer
from app.application.customer.list_customers import ListCustomers
from app.application.customer.register_customer import RegisterCustomer
from app.application.customer.update_customer import UpdateCustomer
from app.application.ports.customer_repository import CustomerQuery
from app.domain.common.contact import Email
from app.domain.common.errors import InvalidValueError
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.customer.value_objects import CustomerId
from tests.factories import make_customer_input

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock


class TestRegisterCustomer:
    async def test_persists_the_customer_and_commits_once(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())

        assert uow.commits == 1
        stored = await uow.customers.get(customer.id)
        assert stored.details.company_name == "네오인"
        assert customer.created_at == clock.now()

    async def test_builds_normalized_value_objects(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        customer = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())

        assert customer.details.email == Email("kim@neoine.example")

    async def test_invalid_input_stores_nothing_and_does_not_commit(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(InvalidValueError):
            await RegisterCustomer(uow_factory, clock).execute(
                make_customer_input(email="not-an-email")
            )

        assert uow.commits == 0
        assert list(await uow.customers.list()) == []


class TestGetCustomer:
    async def test_returns_the_registered_customer_without_committing(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())

        found = await GetCustomer(uow_factory).execute(registered.id)

        assert found == registered
        assert uow.commits == 1  # 등록 때 1번뿐, 조회는 커밋하지 않는다

    async def test_missing_customer_raises_not_found(self, uow_factory: UnitOfWorkFactory) -> None:
        with pytest.raises(CustomerNotFoundError):
            await GetCustomer(uow_factory).execute(_random_customer_id())


class TestListCustomers:
    async def test_lists_in_creation_order_with_paging(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        register = RegisterCustomer(uow_factory, clock)
        created = []
        for number in range(3):
            clock.advance()
            created.append(
                await register.execute(make_customer_input(company_name=f"고객{number}"))
            )

        page = await ListCustomers(uow_factory).execute(CustomerQuery(offset=1, limit=2))

        assert [c.id for c in page] == [created[1].id, created[2].id]

    async def test_excludes_deleted_customers(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        register = RegisterCustomer(uow_factory, clock)
        kept = await register.execute(make_customer_input(company_name="유지"))
        removed = await register.execute(make_customer_input(company_name="삭제"))
        await DeleteCustomer(uow_factory, clock).execute(removed.id)

        listed = await ListCustomers(uow_factory).execute(CustomerQuery())

        assert [c.id for c in listed] == [kept.id]

    async def test_rejects_invalid_paging(self, uow_factory: UnitOfWorkFactory) -> None:
        with pytest.raises(InvalidValueError):
            await ListCustomers(uow_factory).execute(CustomerQuery(limit=0))


class TestUpdateCustomer:
    async def test_replaces_details_and_uses_the_clock(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        clock.advance(300)

        updated = await UpdateCustomer(uow_factory, clock).execute(
            registered.id, make_customer_input(company_name="새 회사", employee_count=None)
        )

        stored = await uow.customers.get(registered.id)
        assert stored.details.company_name == "새 회사"
        assert stored.details.employee_count is None
        assert updated.updated_at == clock.now()
        assert stored.created_at == registered.created_at
        assert uow.commits == 2

    async def test_invalid_input_leaves_the_customer_unchanged(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())

        with pytest.raises(InvalidValueError):
            await UpdateCustomer(uow_factory, clock).execute(
                registered.id, make_customer_input(company_name="  ")
            )

        assert (await uow.customers.get(registered.id)).details.company_name == "네오인"
        assert uow.commits == 1

    async def test_missing_customer_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(CustomerNotFoundError):
            await UpdateCustomer(uow_factory, clock).execute(
                _random_customer_id(), make_customer_input()
            )


class TestDeleteCustomer:
    async def test_soft_deletes_and_hides_the_customer(
        self, uow: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        clock.advance(120)

        await DeleteCustomer(uow_factory, clock).execute(registered.id)

        with pytest.raises(CustomerNotFoundError):
            await GetCustomer(uow_factory).execute(registered.id)
        deleted = await uow.customers.get(registered.id, include_deleted=True)
        assert deleted.deleted_at == clock.now()
        assert uow.commits == 2

    async def test_missing_customer_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        with pytest.raises(CustomerNotFoundError):
            await DeleteCustomer(uow_factory, clock).execute(_random_customer_id())

    async def test_deleting_twice_raises_not_found(
        self, uow_factory: UnitOfWorkFactory, clock: FixedClock
    ) -> None:
        registered = await RegisterCustomer(uow_factory, clock).execute(make_customer_input())
        await DeleteCustomer(uow_factory, clock).execute(registered.id)

        with pytest.raises(CustomerNotFoundError):
            await DeleteCustomer(uow_factory, clock).execute(registered.id)


def _random_customer_id() -> CustomerId:
    return CustomerId(uuid4())
