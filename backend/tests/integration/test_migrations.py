"""마이그레이션과 DB 제약(CHECK, UNIQUE, FK)이 실제 PostgreSQL에서 동작하는지 확인한다."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.support.database import apply_migrations, resolve_admin_url, temporary_database

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {"customers", "partners", "deals", "deal_actions"}


async def _insert_customer(session: AsyncSession, **overrides: object) -> str:
    values: dict[str, object] = {
        "id": uuid4(),
        "company_name": "회사",
        "contact_name": "담당",
        "notes": "",
        "employee_count": None,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into customers (id, company_name, contact_name, notes, employee_count,"
            " created_at, updated_at) values (:id, :company_name, :contact_name, :notes,"
            " :employee_count, now(), now())"
        ),
        values,
    )
    return str(values["id"])


async def _insert_deal(session: AsyncSession, customer_id: str, **overrides: object) -> None:
    values: dict[str, object] = {
        "id": uuid4(),
        "code": "D-1",
        "customer_id": customer_id,
        "amount": 100,
    }
    values.update(overrides)
    await session.execute(
        text(
            "insert into deals (id, code, name, owner, vendor, solution, revenue_amount,"
            " revenue_currency, revenue_date, customer_id, created_at, updated_at)"
            " values (:id, :code, 'n', 'o', 'v', 's', :amount, 'KRW', current_date,"
            " :customer_id, now(), now())"
        ),
        values,
    )


async def test_migrations_create_the_expected_tables(test_database_url: URL) -> None:
    engine = create_async_engine(test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
    finally:
        await engine.dispose()

    assert tables >= EXPECTED_TABLES


async def test_negative_employee_count_is_rejected_by_the_database(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_customers"):
        await _insert_customer(session, employee_count=-1)


async def test_negative_revenue_is_rejected_by_the_database(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)

    with pytest.raises(IntegrityError, match="ck_deals"):
        await _insert_deal(session, customer_id, amount=-1)


async def test_deal_code_is_unique_in_the_database(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    await _insert_deal(session, customer_id, code="SAME")

    with pytest.raises(IntegrityError, match="uq_deals_code"):
        await _insert_deal(session, customer_id, code="SAME")


async def test_deal_must_reference_an_existing_customer(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_deals_customer_id_customers"):
        await _insert_deal(session, str(uuid4()))


async def test_customer_with_deals_cannot_be_physically_deleted(session: AsyncSession) -> None:
    customer_id = await _insert_customer(session)
    await _insert_deal(session, customer_id)

    with pytest.raises(IntegrityError, match="fk_deals_customer_id_customers"):
        await session.execute(text("delete from customers where id = :id"), {"id": customer_id})


async def test_downgrade_and_upgrade_round_trip() -> None:
    admin_url = resolve_admin_url()
    if admin_url is None:
        pytest.skip("관리자 접속 정보가 없어 마이그레이션 왕복 테스트를 건너뜁니다")

    async with temporary_database(admin_url) as url:
        await apply_migrations(url)
        await apply_migrations(url, direction="down", target="base")
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                after_down = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
            assert not (EXPECTED_TABLES & after_down)

            await apply_migrations(url)
            async with engine.connect() as connection:
                after_up = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
        finally:
            await engine.dispose()

    assert after_up >= EXPECTED_TABLES
