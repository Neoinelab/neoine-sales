"""UserRepository 계약(T-P1~P7): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

login_id 유일성은 DB가 아니라 응용 로직(RegisterUser)이 재직자 기준으로 확인한다. 그래서 저장소는
같은 login_id 행(퇴사자 포함, 대소문자 다름 포함)을 거부하지 않고, 조회는 재직 행만 대상으로 한다.
참조 연결(has_links)·물리 삭제 RESTRICT는 test_user_links_contract.py에서 검증한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import pytest_asyncio

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.user.entities import User
from app.domain.user.value_objects import UserDeleteReason, UserId, UserStatusFilter
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.factories_auth import make_resigned_user, make_user
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
    creator = make_user("boss")
    await repository.add(creator)
    user = make_user("kim", Role.ADMIN, created_by_user_id=creator.id, now=NOW)
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.add(user)

    stored = await repository.get(user.id)

    assert stored == user
    assert stored.login_id == LoginId("kim")
    assert stored.role is Role.ADMIN
    assert stored.created_by_user_id == creator.id
    assert stored.display_name == "김영업"
    assert stored.email == "kim@corp.test"
    assert stored.created_at == NOW
    assert stored.updated_at == later(30)
    assert stored.last_login_at == later(30)
    assert stored.deleted_at is None
    assert stored.delete_reason is None
    assert stored.is_active


@pytest.mark.parametrize("role", list(Role))
async def test_every_role_round_trips(repository: UserRepository, role: Role) -> None:
    user = make_user("who", role)
    await repository.add(user)

    assert (await repository.get(user.id)).role is role


async def test_resigned_user_round_trips_with_time_and_reason(repository: UserRepository) -> None:
    user = make_resigned_user("gone", resigned_at=later(60))
    await repository.add(user)

    stored = await repository.get(user.id)

    assert stored.deleted_at == later(60)
    assert stored.delete_reason is UserDeleteReason.RESIGNED
    assert not stored.is_active


async def test_get_unknown_id_raises_not_found(repository: UserRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.get(UserId(uuid4()))


async def test_get_deleted_user_raises_not_found(repository: UserRepository) -> None:
    user = make_user("gone")
    await repository.add(user)
    await repository.delete(user.id)

    with pytest.raises(NotFoundError):
        await repository.get(user.id)


async def test_get_still_returns_a_resigned_user_by_id(repository: UserRepository) -> None:
    user = make_resigned_user("gone")
    await repository.add(user)

    assert (await repository.get(user.id)).id == user.id


async def test_add_rejects_duplicate_primary_key(repository: UserRepository) -> None:
    first = make_user("kim")
    await repository.add(first)
    clone = User.register(
        LoginId("other"),
        Role.USER,
        created_by_user_id=first.id,
        now=NOW,
        entity_id=first.id,
    )

    with pytest.raises(AlreadyExistsError):
        await repository.add(clone)


async def test_add_does_not_enforce_login_id_uniqueness_itself(repository: UserRepository) -> None:
    """유일성은 RegisterUser(재직자 조회 + roster 잠금)의 책임이다. 저장소는 막지 않는다."""
    await repository.add(make_user("kim"))
    await repository.add(make_user("KIM", Role.USER))

    users = await repository.list_users(status=UserStatusFilter.ALL)

    assert len(users) == 2


async def test_login_id_can_be_registered_again_after_the_user_is_deleted(
    repository: UserRepository,
) -> None:
    old = make_user("kim", Role.SALES)
    await repository.add(old)
    await repository.delete(old.id)

    new = make_user("kim", Role.USER, now=later(20))
    await repository.add(new)

    active = await repository.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == new.id
    assert active.role is Role.USER


async def test_get_active_by_login_id_finds_existing_users_only(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)

    found = await repository.get_active_by_login_id(LoginId(" KIM "))
    assert found is not None
    assert found.id == user.id
    assert await repository.get_active_by_login_id(LoginId("nobody")) is None
    await repository.delete(user.id)
    assert await repository.get_active_by_login_id(LoginId("kim")) is None


async def test_get_active_by_login_id_ignores_resigned_rows(repository: UserRepository) -> None:
    await repository.add(make_resigned_user("kim"))

    assert await repository.get_active_by_login_id(LoginId("kim")) is None


async def test_many_resigned_rows_and_one_active_row_share_a_login_id(
    repository: UserRepository,
) -> None:
    await repository.add(make_resigned_user("kim", now=later(1)))
    await repository.add(make_resigned_user("kim", now=later(2)))
    active = make_user("kim", now=later(3))
    await repository.add(active)

    found = await repository.get_active_by_login_id(LoginId("kim"))

    assert found is not None
    assert found.id == active.id
    assert len(await repository.list_users(status=UserStatusFilter.ALL)) == 3


async def test_count_active_admins_drops_after_an_admin_is_deleted(
    repository: UserRepository,
) -> None:
    await repository.add(make_user("a1", Role.ADMIN))
    gone = make_user("a2", Role.ADMIN)
    await repository.add(gone)
    await repository.add(make_user("s1", Role.SALES))
    await repository.add(make_user("u1", Role.USER))
    assert await repository.count_active_admins() == 2
    await repository.delete(gone.id)

    assert await repository.count_active_admins() == 1


async def test_count_active_admins_excludes_resigned_admins(repository: UserRepository) -> None:
    await repository.add(make_user("a1", Role.ADMIN))
    await repository.add(make_resigned_user("a2", Role.ADMIN))

    assert await repository.count_active_admins() == 1


async def test_count_active_admins_is_zero_without_users(repository: UserRepository) -> None:
    assert await repository.count_active_admins() == 0


async def test_update_persists_login_record(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.update(user)
    assert (await repository.get(user.id)).last_login_at == later(30)


async def test_update_persists_resignation(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)
    user.resign(later(60))

    await repository.update(user)

    stored = await repository.get(user.id)
    assert stored.deleted_at == later(60)
    assert stored.delete_reason is UserDeleteReason.RESIGNED
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


async def test_delete_removes_the_row_and_keeps_other_users(repository: UserRepository) -> None:
    gone, kept = make_user("gone"), make_user("kept")
    await repository.add(gone)
    await repository.add(kept)

    await repository.delete(gone.id)

    with pytest.raises(NotFoundError):
        await repository.get(gone.id)
    assert (await repository.get(kept.id)).id == kept.id


async def test_delete_unknown_user_raises_not_found(repository: UserRepository) -> None:
    with pytest.raises(NotFoundError):
        await repository.delete(UserId(uuid4()))


async def test_update_of_a_deleted_user_raises_not_found(repository: UserRepository) -> None:
    user = make_user("kim")
    await repository.add(user)
    await repository.delete(user.id)

    with pytest.raises(NotFoundError):
        await repository.update(user)


async def test_get_for_update_returns_the_user_and_raises_not_found(
    repository: UserRepository,
) -> None:
    user = make_user("kim")
    await repository.add(user)

    assert (await repository.get_for_update(user.id)).id == user.id
    with pytest.raises(NotFoundError):
        await repository.get_for_update(UserId(uuid4()))


async def test_get_for_update_returns_a_resigned_user_too(repository: UserRepository) -> None:
    user = make_resigned_user("gone")
    await repository.add(user)

    assert not (await repository.get_for_update(user.id)).is_active
