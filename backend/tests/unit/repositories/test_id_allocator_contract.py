"""IdAllocator 계약(AC-2·11): Fake와 SQL 구현(실제 PostgreSQL 시퀀스)에 같은 테스트를 적용한다.

`next_id(kind)`는 그 종류 테이블의 id 시퀀스에서 다음 값을 준다(1 이상 2^53-1 이하, 호출마다 증가).
시퀀스는 트랜잭션 밖에 있어서 롤백해도 되돌아가지 않는다(번호가 비는 것은 허용). 종류는 서로
번호를 나누지 않는다. 새 모듈(`IdKind`)은 사용 시점에 가져온다(구현 전에도 수집이 막히지 않게).
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.database import rolled_back_session
from tests.support.ids import MAX_ID

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.engine import URL

    from app.application.ports.unit_of_work import UnitOfWorkFactory

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
KIND_VALUES = {
    "user",
    "session",
    "contact",
    "code",
    "bant_label",
    "action_type",
    "vendor",
    "deal_action",
    "attachment",
    "report",
}


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
    finally:
        await engine.dispose()


async def _next(uow_factory: UnitOfWorkFactory, kind: object) -> int:
    async with uow_factory() as uow:
        return await uow.ids.next_id(kind)  # type: ignore[arg-type]


def test_the_id_kinds_are_exactly_the_tables_the_application_numbers_itself() -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    assert {kind.value for kind in IdKind} == KIND_VALUES


async def test_the_first_id_is_at_least_one(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    assert await _next(uow_factory, IdKind.USER) >= 1


async def test_each_call_returns_a_larger_id(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    ids = [await _next(uow_factory, IdKind.CONTACT) for _ in range(3)]

    assert ids[0] < ids[1] < ids[2]


async def test_ids_stay_within_the_json_safe_range(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    ids = [await _next(uow_factory, kind) for kind in IdKind]

    assert all(1 <= value <= MAX_ID for value in ids)
    assert all(type(value) is int for value in ids)


async def test_ids_of_one_block_keep_increasing(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    async with uow_factory() as uow:
        first = await uow.ids.next_id(IdKind.CODE)
        second = await uow.ids.next_id(IdKind.CODE)

    assert second > first


async def test_kinds_are_numbered_independently(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    first_vendor = await _next(uow_factory, IdKind.VENDOR)
    await _next(uow_factory, IdKind.USER)
    await _next(uow_factory, IdKind.USER)

    assert await _next(uow_factory, IdKind.VENDOR) == first_vendor + 1


async def test_a_rolled_back_allocation_is_not_reused(uow_factory: UnitOfWorkFactory) -> None:
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415

    async with uow_factory() as uow:
        taken = await uow.ids.next_id(IdKind.ATTACHMENT)
        await uow.rollback()  # commit하지 않고 블록을 벗어난다

    assert await _next(uow_factory, IdKind.ATTACHMENT) > taken


@pytest.mark.integration
async def test_an_allocated_id_and_a_database_default_insert_never_collide(
    test_database_url: URL,
) -> None:
    """SQL 전용: 할당받은 id로 넣은 행과 id를 생략한(DB 기본값) 행이 같은 시퀀스를 쓴다."""
    from app.application.ports.id_allocator import IdKind  # noqa: PLC0415
    from app.infra.db.id_allocator import SqlIdAllocator  # noqa: PLC0415

    async with rolled_back_session(test_database_url) as session:
        allocated = await SqlIdAllocator(session).next_id(IdKind.VENDOR)
        await session.execute(
            text(
                "insert into vendors (id, name, created_at, updated_at)"
                " values (:id, 'A', now(), now())"
            ),
            {"id": allocated},
        )
        await session.execute(
            text("insert into vendors (name, created_at, updated_at) values ('B', now(), now())")
        )

        ids = (await session.execute(text("select id from vendors order by name"))).scalars().all()

    assert ids[0] == allocated
    assert ids[1] != allocated
    assert ids[1] > allocated
