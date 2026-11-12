"""UserRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

login_id 유일성은 DB가 아니라 응용 로직(RegisterUser)이 재직자 기준으로 확인한다. 그래서 저장소는
같은 login_id 행(퇴사자 포함, 대소문자 다름 포함)을 거부하지 않고, 조회는 재직 행만 대상으로 한다.
참조 연결(has_links)·물리 삭제 RESTRICT는 test_user_links_contract.py에서 검증한다.
"""

from typing import TYPE_CHECKING

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
from tests.support.ids import new_id

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
    """추가한 사용자를 조회하면 모든 필드가 그대로 돌아온다."""
    # given: 생성자 사용자와 로그인 기록이 있는 사용자
    creator = make_user("boss")
    await repository.add(creator)
    user = make_user("kim", Role.ADMIN, created_by_user_id=creator.id, now=NOW)
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.add(user)

    # when: 사용자를 조회한다
    stored = await repository.get(user.id)

    # then: 모든 필드가 저장한 값과 같다
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
    """모든 역할이 저장 후 그대로 조회된다."""
    # given: 해당 역할의 사용자
    user = make_user("who", role)
    await repository.add(user)

    # when: 저장한 사용자를 다시 조회한다
    result = (await repository.get(user.id)).role
    # then: 역할이 저장한 값과 같다
    assert result is role


async def test_resigned_user_round_trips_with_time_and_reason(repository: UserRepository) -> None:
    """퇴사자는 퇴사 시각과 사유가 보존된다."""
    # given: 퇴사 처리된 사용자
    user = make_resigned_user("gone", resigned_at=later(60))
    await repository.add(user)

    # when: 조회한다
    stored = await repository.get(user.id)

    # then: 퇴사 시각·사유가 보존되고 재직 상태가 아니다
    assert stored.deleted_at == later(60)
    assert stored.delete_reason is UserDeleteReason.RESIGNED
    assert not stored.is_active


async def test_get_unknown_id_raises_not_found(repository: UserRepository) -> None:
    """없는 id를 조회하면 찾을 수 없다."""
    # when·then: 없는 id로 조회하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.get(UserId(new_id()))


async def test_get_deleted_user_raises_not_found(repository: UserRepository) -> None:
    """삭제된 사용자를 조회하면 찾을 수 없다."""
    # given: 저장 뒤 삭제한 사용자
    user = make_user("gone")
    await repository.add(user)
    await repository.delete(user.id)

    # when·then: 조회하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.get(user.id)


async def test_get_still_returns_a_resigned_user_by_id(repository: UserRepository) -> None:
    """퇴사자는 id로 계속 조회된다."""
    # given: 저장된 퇴사자
    user = make_resigned_user("gone")
    await repository.add(user)

    # when: id로 조회한다
    result = (await repository.get(user.id)).id
    # then: 그 사용자다
    assert result == user.id


async def test_add_rejects_duplicate_primary_key(repository: UserRepository) -> None:
    """같은 PK로 추가하면 거부한다."""
    # given: 저장된 사용자와 같은 id를 가진 다른 사용자
    first = make_user("kim")
    await repository.add(first)
    clone = User.register(
        LoginId("other"),
        Role.USER,
        created_by_user_id=first.id,
        now=NOW,
        entity_id=first.id,
    )

    # when·then: 추가하면 이미 있음 오류다
    with pytest.raises(AlreadyExistsError):
        await repository.add(clone)


async def test_add_does_not_enforce_login_id_uniqueness_itself(repository: UserRepository) -> None:
    """저장소는 로그인 아이디 유일성을 스스로 막지 않는다(RegisterUser의 책임이다)."""
    # given: 같은 아이디(대소문자만 다름)의 사용자 둘을 추가한다
    await repository.add(make_user("kim"))
    await repository.add(make_user("KIM", Role.USER))

    # when: 전체 사용자를 조회한다
    users = await repository.list_users(status=UserStatusFilter.ALL)

    # then: 둘 다 저장돼 있다
    assert len(users) == 2


async def test_login_id_can_be_registered_again_after_the_user_is_deleted(
    repository: UserRepository,
) -> None:
    """사용자가 삭제된 뒤 같은 로그인 아이디를 다시 등록할 수 있다."""
    # given: 저장 뒤 삭제한 사용자
    old = make_user("kim", Role.SALES)
    await repository.add(old)
    await repository.delete(old.id)

    # when: 같은 아이디의 새 사용자를 추가한다
    new = make_user("kim", Role.USER, now=later(20))
    await repository.add(new)

    # then: 재직 조회가 새 사용자를 돌려준다
    active = await repository.get_active_by_login_id(LoginId("kim"))
    assert active is not None
    assert active.id == new.id
    assert active.role is Role.USER


async def test_get_active_by_login_id_finds_existing_users_only(repository: UserRepository) -> None:
    """재직 조회는 존재하는 사용자만 찾는다."""
    # given: 저장된 사용자 (재직 조회)
    user = make_user("kim")
    await repository.add(user)

    # when: 공백·대소문자가 다른 아이디로 조회한다
    found = await repository.get_active_by_login_id(LoginId(" KIM "))
    # then: 그 사용자를 찾는다
    assert found is not None
    assert found.id == user.id
    # when: 없는 아이디로 재직 사용자를 조회한다
    result = await repository.get_active_by_login_id(LoginId("nobody"))
    # then: None이다
    assert result is None
    # when: 사용자를 삭제한다
    await repository.delete(user.id)
    # then: 삭제 뒤에는 찾지 못한다
    assert await repository.get_active_by_login_id(LoginId("kim")) is None


async def test_get_active_by_login_id_ignores_resigned_rows(repository: UserRepository) -> None:
    """재직 조회는 퇴사자 행을 무시한다."""
    # given: 퇴사한 사용자
    await repository.add(make_resigned_user("kim"))

    # when: 그 아이디로 재직 조회한다
    result = await repository.get_active_by_login_id(LoginId("kim"))
    # then: None이다
    assert result is None


async def test_many_resigned_rows_and_one_active_row_share_a_login_id(
    repository: UserRepository,
) -> None:
    """퇴사자 여러 행과 재직자 한 행이 같은 아이디를 공유할 수 있다."""
    # given: 같은 아이디의 퇴사자 둘과 재직자 하나
    await repository.add(make_resigned_user("kim", now=later(1)))
    await repository.add(make_resigned_user("kim", now=later(2)))
    active = make_user("kim", now=later(3))
    await repository.add(active)

    # when: 재직 조회한다
    found = await repository.get_active_by_login_id(LoginId("kim"))

    # then: 재직자를 찾고 전체는 3행이다
    assert found is not None
    assert found.id == active.id
    assert len(await repository.list_users(status=UserStatusFilter.ALL)) == 3


async def test_count_active_admins_drops_after_an_admin_is_deleted(
    repository: UserRepository,
) -> None:
    """admin을 삭제하면 재직 admin 수가 줄어든다."""
    # given: admin 둘, sales와 user 각 하나
    await repository.add(make_user("a1", Role.ADMIN))
    gone = make_user("a2", Role.ADMIN)
    await repository.add(gone)
    await repository.add(make_user("s1", Role.SALES))
    await repository.add(make_user("u1", Role.USER))
    # when: 삭제 전 재직 admin 수를 센다
    before = await repository.count_active_admins()
    # then: 재직 admin은 2명이다
    assert before == 2
    # when: admin 한 명을 삭제한다
    await repository.delete(gone.id)

    # then: 재직 admin은 1명이다
    assert await repository.count_active_admins() == 1


async def test_count_active_admins_excludes_resigned_admins(repository: UserRepository) -> None:
    """재직 admin 수에서 퇴사한 admin은 뺀다."""
    # given: 재직 admin 하나와 퇴사 admin 하나
    await repository.add(make_user("a1", Role.ADMIN))
    await repository.add(make_resigned_user("a2", Role.ADMIN))

    # when: 재직 admin 수를 센다
    result = await repository.count_active_admins()
    # then: 1이다
    assert result == 1


async def test_count_active_admins_is_zero_without_users(repository: UserRepository) -> None:
    """사용자가 없으면 재직 admin 수는 0이다."""
    # when: 재직 admin 수를 센다
    result = await repository.count_active_admins()
    # then: 0이다
    assert result == 0


async def test_update_persists_login_record(repository: UserRepository) -> None:
    """update는 로그인 기록을 저장한다."""
    # given: 저장된 사용자 (로그인 기록 저장)
    user = make_user("kim")
    await repository.add(user)
    # when: 로그인을 기록하고 update한다
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")
    await repository.update(user)
    # then: 마지막 로그인 시각이 저장돼 있다
    assert (await repository.get(user.id)).last_login_at == later(30)


async def test_update_persists_resignation(repository: UserRepository) -> None:
    """update는 퇴사 처리를 저장한다."""
    # given: 저장된 사용자 (퇴사 처리 저장)
    user = make_user("kim")
    await repository.add(user)
    # when: 퇴사 처리하고 update한다
    user.resign(later(60))

    await repository.update(user)

    # then: 퇴사 시각·사유가 저장되고 재직 조회에서 빠진다
    stored = await repository.get(user.id)
    assert stored.deleted_at == later(60)
    assert stored.delete_reason is UserDeleteReason.RESIGNED
    assert await repository.get_active_by_login_id(LoginId("kim")) is None


@pytest.mark.parametrize(("before", "after"), [(Role.SALES, Role.USER), (Role.USER, Role.ADMIN)])
async def test_update_persists_role_change(
    repository: UserRepository, before: Role, after: Role
) -> None:
    """update는 역할 변경을 저장한다."""
    # given: 저장된 사용자 (역할 변경 저장)
    user = make_user("kim", before)
    await repository.add(user)
    # when: 역할을 바꾸고 update한다
    user.change_role(after, later(30))

    await repository.update(user)

    # then: 새 역할과 수정 시각이 저장되고 재직 조회도 된다
    stored = await repository.get(user.id)
    assert stored.role is after
    assert stored.updated_at == later(30)
    assert (await repository.get_active_by_login_id(LoginId("kim"))) is not None


async def test_role_change_moves_the_user_between_admin_counts(repository: UserRepository) -> None:
    """역할 변경은 재직 admin 수에 반영된다."""
    # given: admin 하나와 sales 하나
    boss = make_user("boss", Role.ADMIN)
    kim = make_user("kim", Role.SALES)
    await repository.add(boss)
    await repository.add(kim)
    # when: sales를 admin으로 바꾼다
    kim.change_role(Role.ADMIN, later(1))
    await repository.update(kim)
    # then: 재직 admin이 2명이다
    assert await repository.count_active_admins() == 2

    # when: 기존 admin을 user로 바꾼다
    boss.change_role(Role.USER, later(2))
    await repository.update(boss)

    # then: 재직 admin이 1명이다
    assert await repository.count_active_admins() == 1


async def test_update_unknown_user_raises_not_found(repository: UserRepository) -> None:
    """없는 사용자를 update하면 찾을 수 없다."""
    # when·then: 저장되지 않은 사용자를 update하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.update(make_user("ghost"))


async def test_returned_users_are_copies(repository: UserRepository) -> None:
    """돌려준 사용자를 바꿔도 저장소에는 영향이 없다."""
    # given: 저장된 사용자 (복사본 확인)
    user = make_user("kim")
    await repository.add(user)
    fetched = await repository.get(user.id)
    # when: 조회한 객체를 바꾼다
    fetched.record_login(later(5), display_name="바뀜", email=None)

    # then: 다시 조회한 표시 이름은 그대로 비어 있다
    assert (await repository.get(user.id)).display_name is None


async def test_lock_roster_can_be_called_repeatedly(repository: UserRepository) -> None:
    """명단 잠금을 반복해서 호출할 수 있다."""
    # when·then: 두 번 호출해도 오류 없이 끝난다
    await repository.lock_roster()
    await repository.lock_roster()


async def test_delete_removes_the_row_and_keeps_other_users(repository: UserRepository) -> None:
    """삭제는 해당 행만 지우고 다른 사용자는 남긴다."""
    # given: 저장된 사용자 둘
    gone, kept = make_user("gone"), make_user("kept")
    await repository.add(gone)
    await repository.add(kept)

    # when: 한 명을 삭제한다
    await repository.delete(gone.id)

    # then: 삭제한 사용자는 조회되지 않는다
    with pytest.raises(NotFoundError):
        await repository.get(gone.id)
    # then: 남긴 사용자는 조회된다
    assert (await repository.get(kept.id)).id == kept.id


async def test_delete_unknown_user_raises_not_found(repository: UserRepository) -> None:
    """없는 사용자를 삭제하면 찾을 수 없다."""
    # when·then: 없는 id를 삭제하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.delete(UserId(new_id()))


async def test_update_of_a_deleted_user_raises_not_found(repository: UserRepository) -> None:
    """삭제된 사용자를 update하면 찾을 수 없다."""
    # given: 저장 뒤 삭제한 사용자
    user = make_user("kim")
    await repository.add(user)
    await repository.delete(user.id)

    # when·then: update하면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.update(user)


async def test_get_for_update_returns_the_user_and_raises_not_found(
    repository: UserRepository,
) -> None:
    """get_for_update는 사용자를 돌려주고 없으면 찾을 수 없다."""
    # given: 저장된 사용자 (잠금 조회)
    user = make_user("kim")
    await repository.add(user)

    # when: 잠금을 걸어 사용자를 조회한다
    result = (await repository.get_for_update(user.id)).id
    # then: 그 사용자를 돌려준다
    assert result == user.id
    # when·then: 없는 id면 없음 오류다
    with pytest.raises(NotFoundError):
        await repository.get_for_update(UserId(new_id()))


async def test_get_for_update_returns_a_resigned_user_too(repository: UserRepository) -> None:
    """get_for_update는 퇴사자도 돌려준다."""
    # given: 저장된 퇴사자
    user = make_resigned_user("gone")
    await repository.add(user)

    # when: 잠금을 걸어 퇴사자를 조회한다
    result = (await repository.get_for_update(user.id)).is_active
    # then: 퇴사자를 돌려주며 재직 상태가 아니다
    assert not result
