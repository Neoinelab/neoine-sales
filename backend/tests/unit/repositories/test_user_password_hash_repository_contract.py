"""UserPasswordHashRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

사용자 id 하나에 해시 행 하나(upsert). 사용자가 없으면 UserNotFoundError(FK 위반을 변환).
사용자를 물리 삭제하면 해시도 함께 사라지고(ON DELETE CASCADE), 해시는 삭제를 막는 연결이 아니다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.auth.password_hash import PasswordHash
from app.domain.user.errors import UserNotFoundError
from app.infra.db.unit_of_work import sql_unit_of_work_factory
from tests.factories import NOW, later
from tests.factories_auth import make_user
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.support.ids import new_id
from tests.support.truncate import truncate_business_tables

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from datetime import datetime

    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from app.domain.user.entities import User

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
FIRST = PasswordHash(
    "scrypt$ln=14,r=8,p=1$c2FsdC0xc2FsdC0xc2FsdA$aGFzaC0xaGFzaC0xaGFzaC0xaGFzaC0xaGFzaC0x"
)
SECOND = PasswordHash(
    "scrypt$ln=14,r=8,p=1$c2FsdC0yc2FsdC0yc2FsdA$aGFzaC0yaGFzaC0yaGFzaC0yaGFzaC0yaGFzaC0y"
)


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
            await truncate_business_tables(connection)
    finally:
        await engine.dispose()


async def _user(uow_factory: UnitOfWorkFactory, login_id: str = "kim") -> User:
    user = make_user(login_id)
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()
    return user


async def _save(
    uow_factory: UnitOfWorkFactory, user: User, value: PasswordHash, at: datetime = NOW
) -> None:
    async with uow_factory() as uow:
        await uow.password_hashes.save(user.id, value, at)
        await uow.commit()


async def _get(uow_factory: UnitOfWorkFactory, user: User) -> PasswordHash | None:
    async with uow_factory() as uow:
        return await uow.password_hashes.get(user.id)


async def test_save_then_get_round_trips(uow_factory: UnitOfWorkFactory) -> None:
    """저장한 해시를 그대로 다시 읽는다."""
    # given: 저장된 사용자
    user = await _user(uow_factory)

    # when: 해시를 저장하고 조회한다 (전제: Fake·SQL 저장소 공통)
    await _save(uow_factory, user, FIRST)

    stored = await _get(uow_factory, user)

    # then: 저장한 해시다
    assert stored == FIRST


async def test_save_overwrites_existing_hash(uow_factory: UnitOfWorkFactory) -> None:
    """같은 사용자의 해시를 다시 저장하면 덮어쓴다."""
    # given: 해시가 저장된 사용자
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    # when: 다른 해시를 저장하고 조회한다 (전제: Fake·SQL 저장소 공통)
    await _save(uow_factory, user, SECOND, later(60))

    stored = await _get(uow_factory, user)

    # then: 새 해시다
    assert stored == SECOND


async def test_get_missing_returns_none(uow_factory: UnitOfWorkFactory) -> None:
    """저장하지 않은 사용자의 해시는 None이다."""
    # given: 해시를 저장하지 않은 사용자
    user = await _user(uow_factory)

    # when: 해시를 조회한다 (전제: Fake·SQL 저장소 공통)
    stored = await _get(uow_factory, user)

    # then: None이다
    assert stored is None


async def test_hashes_are_kept_per_user(uow_factory: UnitOfWorkFactory) -> None:
    """해시는 사용자마다 따로 보관한다."""
    # given: 사용자 둘 중 한 명만 해시를 저장한 상태
    kim = await _user(uow_factory, "kim")
    lee = await _user(uow_factory, "lee")
    await _save(uow_factory, kim, FIRST)

    # when: 다른 사용자의 해시를 조회한다 (전제: Fake·SQL 저장소 공통)
    lee_before = await _get(uow_factory, lee)
    # then: 저장하지 않은 사용자는 None이다
    assert lee_before is None
    # when: 그 사용자도 해시를 저장하고 둘을 조회한다
    await _save(uow_factory, lee, SECOND)

    kim_hash = await _get(uow_factory, kim)
    lee_hash = await _get(uow_factory, lee)
    # then: 각자 자기 해시를 가진다
    assert kim_hash == FIRST
    assert lee_hash == SECOND


async def test_delete_removes_only_that_users_hash(uow_factory: UnitOfWorkFactory) -> None:
    """삭제는 해당 사용자의 해시만 지운다."""
    # given: 해시를 저장한 사용자 둘
    kim = await _user(uow_factory, "kim")
    lee = await _user(uow_factory, "lee")
    await _save(uow_factory, kim, FIRST)
    await _save(uow_factory, lee, SECOND)

    # when: 한 사용자의 해시를 삭제하고 둘을 조회한다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        await uow.password_hashes.delete(kim.id)
        await uow.commit()

    kim_hash = await _get(uow_factory, kim)
    lee_hash = await _get(uow_factory, lee)

    # then: 삭제한 사용자는 None이고 다른 사용자의 해시는 남는다
    assert kim_hash is None
    assert lee_hash == SECOND


async def test_delete_missing_is_not_error(uow_factory: UnitOfWorkFactory) -> None:
    """해시가 없는 사용자의 삭제는 오류가 아니다."""
    # given: 해시가 없는 사용자
    user = await _user(uow_factory)

    # when: 해시를 삭제한다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        await uow.password_hashes.delete(user.id)  # 예외가 없으면 통과
        await uow.commit()

    stored = await _get(uow_factory, user)

    # then: 오류 없이 해시는 없는 상태다
    assert stored is None


async def test_save_for_missing_user_raises_user_not_found(uow_factory: UnitOfWorkFactory) -> None:
    """없는 사용자의 해시 저장은 사용자 없음 오류다."""
    # when·then: 없는 사용자 id로 저장하면 UserNotFoundError가 난다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        with pytest.raises(UserNotFoundError):
            await uow.password_hashes.save(new_id(), FIRST, NOW)  # type: ignore[arg-type]


async def test_uncommitted_save_is_discarded(uow_factory: UnitOfWorkFactory) -> None:
    """커밋하지 않은 저장은 버려진다."""
    # given: 해시가 없는 사용자
    user = await _user(uow_factory)

    # when: 저장만 하고 커밋하지 않은 채 트랜잭션을 닫는다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        await uow.password_hashes.save(user.id, FIRST, NOW)

    stored = await _get(uow_factory, user)

    # then: 해시는 저장되지 않았다
    assert stored is None


async def test_password_hash_does_not_count_as_link(uow_factory: UnitOfWorkFactory) -> None:
    """비밀번호 해시는 사용자 삭제를 막는 연결이 아니다."""
    # given: 해시가 저장된 사용자
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    # when: 사용자의 연결 여부를 묻는다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        has_links = await uow.users.has_links(user.id)

    # then: 연결이 없다
    assert has_links is False


async def test_physical_delete_cascades_password_hash(uow_factory: UnitOfWorkFactory) -> None:
    """사용자를 물리 삭제하면 해시도 함께 사라진다."""
    # given: 해시가 저장된 사용자
    user = await _user(uow_factory)
    await _save(uow_factory, user, FIRST)

    # when: 사용자를 물리 삭제한다 (전제: Fake·SQL 저장소 공통)
    async with uow_factory() as uow:
        await uow.users.delete(user.id)  # 해시가 있어도 막히지 않는다
        await uow.commit()

    stored = await _get(uow_factory, user)

    # then: 해시도 없다
    assert stored is None
