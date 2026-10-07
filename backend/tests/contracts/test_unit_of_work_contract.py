"""UnitOfWork 공통 계약: commit한 변경만 남고, 미커밋·예외·commit 이후의 변경은 사라진다.

Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다. SQL 구현은 실제로 commit하므로
테스트가 끝나면 테이블을 비워 다른 테스트에 영향을 주지 않는다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.customer.errors import CustomerNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import make_customer
from tests.fakes.unit_of_work import FakeUnitOfWork

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.customer.entities import Customer

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def uow_factory(request: pytest.FixtureRequest) -> AsyncIterator[UnitOfWorkFactory]:
    if request.param == "fake":
        shared = FakeUnitOfWork()
        yield lambda: shared
        return
    url = request.getfixturevalue("test_database_url")
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        yield sql_unit_of_work_factory(async_sessionmaker(engine, expire_on_commit=False))
        async with engine.begin() as connection:
            await connection.execute(
                text("truncate auth_sessions, deal_actions, deals, customers, partners cascade")
            )
    finally:
        await engine.dispose()


async def test_committed_changes_are_visible_to_later_units(
    uow_factory: UnitOfWorkFactory,
) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        await uow.commit()

    async with uow_factory() as later_uow:
        assert await later_uow.customers.get(customer.id) == customer


async def test_changes_are_visible_inside_the_unit_before_commit(
    uow_factory: UnitOfWorkFactory,
) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)

        assert await uow.customers.get(customer.id) == customer


async def test_changes_without_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)

    async with uow_factory() as later_uow:
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(customer.id)


async def _add_then_fail(uow_factory: UnitOfWorkFactory, customer: Customer) -> None:
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        raise RuntimeError("boom")


async def test_an_exception_discards_changes_even_after_add(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    with pytest.raises(RuntimeError, match="boom"):
        await _add_then_fail(uow_factory, customer)

    async with uow_factory() as later_uow:
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(customer.id)


async def test_explicit_rollback_discards_changes(uow_factory: UnitOfWorkFactory) -> None:
    customer = make_customer()
    async with uow_factory() as uow:
        await uow.customers.add(customer)
        await uow.rollback()

        with pytest.raises(CustomerNotFoundError):
            await uow.customers.get(customer.id)


async def test_changes_made_after_commit_are_discarded(uow_factory: UnitOfWorkFactory) -> None:
    kept, dropped = make_customer(company_name="유지"), make_customer(company_name="폐기")
    async with uow_factory() as uow:
        await uow.customers.add(kept)
        await uow.commit()
        await uow.customers.add(dropped)

    async with uow_factory() as later_uow:
        assert await later_uow.customers.get(kept.id) == kept
        with pytest.raises(CustomerNotFoundError):
            await later_uow.customers.get(dropped.id)
