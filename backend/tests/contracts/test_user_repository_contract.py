"""UserRepository 계약(T-P1~P7): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, InvalidValueError, NotFoundError
from app.domain.user.entities import User
from app.domain.user.value_objects import UserId
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.factories_auth import make_user
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.user_repository import UserRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[UserRepository]:
    if request.param == "fake":
        yield FakeUserRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlUserRepository(session)


async def test_add_then_get_round_trips_every_field(repository: UserRepository) -> None:
    user = make_user("kim", Role.ADMIN, created_by="boss", now=NOW)
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.add(user)

    stored = await repository.get(user.id)

    assert stored == user
    assert stored.login_id == LoginId("kim")
    assert stored.role is Role.ADMIN
    assert stored.created_by == "boss"
    assert stored.display_name == "김영업"
    assert stored.email == "kim@corp.test"
    assert stored.created_at == NOW
    assert stored.updated_at == later(30)
    assert stored.last_login_at == later(30)
    assert stored.deleted_at is None


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_round_trips(repository: UserRepository, role: Role) -> None:
    user = make_user("who", role)
    await repository.add(user)

    assert (await repository.get(user.id)).role is role


async def test_get_unknown_id_raises_not_found(repository: UserRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.get(UserId(uuid4()))


async def test_get_deleted_user_raises_not_found(repository: UserRepository) -> None:
    user = make_user("gone")
    await repository.add(user)
    user.soft_delete(later(5))
    await repository.update(user)

    with pytest.raises(NotFoundError):
        await repository.get(user.id)


async def test_add_rejects_second_active_user_with_same_login_id(
    repository: UserRepository,
) -> None:
    await repository.add(make_user("kim"))

    with pytest.raises(AlreadyExistsError):
        await repository.add(make_user("kim", Role.USER))


async def test_add_rejects_duplicate_primary_key(repository: UserRepository) -> None:
    first = make_user("kim")
    await repository.add(first)
    clone = User.register(
        LoginId("other"), Role.USER, created_by="admin", now=NOW, entity_id=first.id
    )

    with pytest.raises(AlreadyExistsError):
        await repository.add(clone)


async def test_login_id_can_be_registered_again_after_soft_delete(
    repository: UserRepository,
) -> None:
    old = make_user("kim", Role.SALES)
    await repository.add(old)
    old.soft_delete(later(10))
    await repository.update(old)

    new = make_user("kim", Role.USER, now=later(20))
    await repository.add(new)

    active = await repository.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == new.id
    assert active.role is Role.USER


async def test_get_active_by_login_id_finds_only_active_users(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)

    found = await repository.get_active_by_login_id(LoginId(" KIM "))
    assert found is not None
    assert found.id == user.id
    assert await repository.get_active_by_login_id(LoginId("nobody")) is None
    user.soft_delete(later(1))
    await repository.update(user)
    assert await repository.get_active_by_login_id(LoginId("kim")) is None


async def test_list_active_excludes_deleted_and_orders_by_creation(
    repository: UserRepository,
) -> None:
    third = make_user("c", now=later(30))
    first = make_user("a", now=later(10))
    deleted = make_user("d", now=later(20))
    second = make_user("b", now=later(20))
    for user in (third, first, deleted, second):
        await repository.add(user)
    deleted.soft_delete(later(40))
    await repository.update(deleted)

    listed = await repository.list_active()

    assert [u.login_id.value for u in listed] == ["a", "b", "c"]


async def test_list_active_applies_offset_and_limit(repository: UserRepository) -> None:
    for n in range(5):
        await repository.add(make_user(f"user{n}", now=later(n)))

    page = await repository.list_active(offset=1, limit=2)

    assert [u.login_id.value for u in page] == ["user1", "user2"]


@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_active_rejects_invalid_page(
    repository: UserRepository, offset: int, limit: int
) -> None:
    with pytest.raises(InvalidValueError):
        await repository.list_active(offset=offset, limit=limit)


async def test_count_active_admins_counts_only_active_admins(repository: UserRepository) -> None:
    await repository.add(make_user("a1", Role.ADMIN))
    gone = make_user("a2", Role.ADMIN)
    await repository.add(gone)
    await repository.add(make_user("s1", Role.SALES))
    await repository.add(make_user("u1", Role.USER))
    assert await repository.count_active_admins() == 2
    gone.soft_delete(later(5))
    await repository.update(gone)

    assert await repository.count_active_admins() == 1


async def test_count_active_admins_is_zero_without_users(repository: UserRepository) -> None:
    assert await repository.count_active_admins() == 0


async def test_update_persists_login_record_and_soft_delete(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.update(user)
    assert (await repository.get(user.id)).last_login_at == later(30)

    user.soft_delete(later(60))
    await repository.update(user)

    assert await repository.get_active_by_login_id(LoginId("kim")) is None


async def test_update_unknown_user_raises_not_found(repository: UserRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.update(make_user("ghost"))


async def test_returned_users_are_copies(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)
    fetched = await repository.get(user.id)
    fetched.record_login(later(5), display_name="바뀜", email=None)

    assert (await repository.get(user.id)).display_name is None


async def test_lock_roster_can_be_called_repeatedly(repository: UserRepository) -> None:
    await repository.lock_roster()
    await repository.lock_roster()
