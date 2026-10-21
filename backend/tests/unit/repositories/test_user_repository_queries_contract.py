"""UserRepository 조회 계약: 상태별 목록, UserRef 일괄 조회, 사용자 선택 검색(Fake와 SQL 공통)."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.common.errors import InvalidValueError
from app.domain.user.value_objects import UserId, UserStatusFilter
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import later
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


async def test_list_users_defaults_to_active_in_creation_order(repository: UserRepository) -> None:
    third = make_user("c", now=later(30))
    first = make_user("a", now=later(10))
    deleted = make_user("d", now=later(20))
    resigned = make_resigned_user("r", now=later(25))
    second = make_user("b", now=later(20))
    for user in (third, first, deleted, resigned, second):
        await repository.add(user)
    await repository.delete(deleted.id)

    listed = await repository.list_users()

    assert [u.login_id.value for u in listed] == ["a", "b", "c"]


async def test_list_users_by_status(repository: UserRepository) -> None:
    await repository.add(make_user("a", now=later(1)))
    await repository.add(make_resigned_user("r1", now=later(2)))
    await repository.add(make_user("b", now=later(3)))
    await repository.add(make_resigned_user("r2", now=later(4)))

    active = await repository.list_users(status=UserStatusFilter.ACTIVE)
    resigned = await repository.list_users(status=UserStatusFilter.RESIGNED)
    everyone = await repository.list_users(status=UserStatusFilter.ALL)

    assert [u.login_id.value for u in active] == ["a", "b"]
    assert [u.login_id.value for u in resigned] == ["r1", "r2"]
    assert [u.login_id.value for u in everyone] == ["a", "r1", "b", "r2"]


async def test_list_users_applies_offset_and_limit(repository: UserRepository) -> None:
    for n in range(5):
        await repository.add(make_user(f"user{n}", now=later(n)))

    page = await repository.list_users(offset=1, limit=2)

    assert [u.login_id.value for u in page] == ["user1", "user2"]


@pytest.mark.parametrize("status", list(UserStatusFilter))
@pytest.mark.parametrize(("offset", "limit"), [(-1, 10), (0, 0), (0, 201)])
async def test_list_users_rejects_invalid_page(
    repository: UserRepository, status: UserStatusFilter, offset: int, limit: int
) -> None:
    with pytest.raises(InvalidValueError):
        await repository.list_users(status=status, offset=offset, limit=limit)


async def test_get_refs_resolves_active_and_resigned_users_in_one_call(
    repository: UserRepository,
) -> None:
    active = make_user("hong")
    active.record_login(later(1), display_name="홍길동", email=None)
    leaver = make_user("leaver")
    leaver.record_login(later(1), display_name="이탈자", email=None)
    leaver.resign(later(2))
    await repository.add(active)
    await repository.add(leaver)

    refs = await repository.get_refs([active.id, leaver.id])

    assert refs[active.id].label == "홍길동"
    assert refs[active.id].name == "홍길동"
    assert refs[active.id].resigned is False
    assert refs[leaver.id].label == "이탈자(퇴사)"
    assert refs[leaver.id].resigned is True


async def test_get_refs_falls_back_to_login_id_and_skips_unknown_ids(
    repository: UserRepository,
) -> None:
    user = make_user("newbie")
    await repository.add(user)
    unknown = UserId(new_id())

    refs = await repository.get_refs([user.id, unknown, user.id])

    assert set(refs) == {user.id}
    assert refs[user.id].name == "newbie"


async def test_get_refs_of_nothing_is_empty(repository: UserRepository) -> None:
    assert dict(await repository.get_refs([])) == {}


async def test_search_refs_filters_by_keyword_and_resigned_flag(repository: UserRepository) -> None:
    hong = make_user("hong.gd", now=later(1))
    hong.record_login(later(1), display_name="홍길동", email="hong@corp.test")
    kim = make_user("kim", now=later(2))
    kim.record_login(later(2), display_name="김영업", email=None)
    leaver = make_user("hong.old", now=later(3))
    leaver.record_login(later(3), display_name="홍이탈", email=None)
    leaver.resign(later(4))
    for user in (hong, kim, leaver):
        await repository.add(user)

    active_hong = await repository.search_refs(keyword="홍", include_resigned=False, limit=10)
    all_hong = await repository.search_refs(keyword="홍", include_resigned=True, limit=10)
    everyone_active = await repository.search_refs(keyword=None, include_resigned=False, limit=10)

    assert [r.id for r in active_hong] == [hong.id]
    assert [r.id for r in all_hong] == [hong.id, leaver.id]
    assert [r.id for r in everyone_active] == [hong.id, kim.id]


async def test_search_refs_matches_the_display_name_not_the_login_id(
    repository: UserRepository,
) -> None:
    hong = make_user("hong.gd", now=later(1))
    hong.record_login(later(1), display_name="홍길동", email=None)
    await repository.add(hong)

    by_login_id = await repository.search_refs(keyword="HONG", include_resigned=True, limit=10)
    by_full_login_id = await repository.search_refs(
        keyword="hong.gd", include_resigned=True, limit=10
    )

    assert by_login_id == []
    assert by_full_login_id == []


async def test_search_refs_matches_the_login_id_only_as_the_fallback_name(
    repository: UserRepository,
) -> None:
    newbie = make_user("newbie", now=later(1))  # 표시 이름 없음: name == login_id
    await repository.add(newbie)

    refs = await repository.search_refs(keyword="NEWB", include_resigned=False, limit=10)

    assert [(r.id, r.name) for r in refs] == [(newbie.id, "newbie")]


async def test_search_refs_respects_the_limit_in_creation_order(repository: UserRepository) -> None:
    for n in range(5):
        await repository.add(make_user(f"user{n}", now=later(n)))

    refs = await repository.search_refs(keyword=None, include_resigned=False, limit=3)

    assert [r.name for r in refs] == ["user0", "user1", "user2"]


async def test_search_refs_treats_like_wildcards_literally(repository: UserRepository) -> None:
    await repository.add(make_user("a_b", now=later(1)))
    await repository.add(make_user("axb", now=later(2)))

    refs = await repository.search_refs(keyword="a_b", include_resigned=False, limit=10)

    assert [r.name for r in refs] == ["a_b"]
