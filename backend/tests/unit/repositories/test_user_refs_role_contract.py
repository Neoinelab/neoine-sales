"""UserRepository의 UserRef 조회는 role을 담고 search_refs는 role로 거른다.

같은 계약을 InMemory Fake와 SQL 구현 양쪽에 돌린다.
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.auth.principal import Role
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user
from tests.fakes.user_repository import FakeUserRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.user_repository import UserRepository
    from app.domain.user.entities import User

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


async def _seed(repository: UserRepository) -> list[User]:
    users = [
        make_user("root", Role.ADMIN, now=later(1)),
        make_user("sales1", Role.SALES, now=later(2)),
        make_user("viewer", Role.USER, now=later(3)),
        make_resigned_user("gone", Role.SALES, now=later(4)),
    ]
    for user in users:
        await repository.add(user)
    return users


async def test_get_refs_carries_the_role_of_each_user_including_resigned(
    repository: UserRepository,
) -> None:
    """get_refs는 퇴사자를 포함해 사용자마다 역할을 담는다."""
    # given: 역할이 다른 사용자 넷(퇴사자 포함)
    users = await _seed(repository)

    # when: 참조를 조회한다
    refs = await repository.get_refs([u.id for u in users])

    # then: 이름별 역할이 기대와 같다
    assert {r.name: r.role for r in refs.values()} == {
        "root": Role.ADMIN,
        "sales1": Role.SALES,
        "viewer": Role.USER,
        "gone": Role.SALES,
    }


async def test_search_refs_carries_the_role_of_each_user(repository: UserRepository) -> None:
    """search_refs는 사용자마다 역할을 담는다."""
    # given: 역할이 다른 사용자 넷(퇴사자 포함)
    await _seed(repository)

    # when: 퇴사자 제외로 검색한다
    refs = await repository.search_refs(keyword=None, include_resigned=False, limit=10)

    # then: 재직자의 이름과 역할이 등록 순서로 나온다
    assert [(r.name, r.role) for r in refs] == [
        ("root", Role.ADMIN),
        ("sales1", Role.SALES),
        ("viewer", Role.USER),
    ]


async def test_search_refs_with_role_returns_only_active_users_of_that_role(
    repository: UserRepository,
) -> None:
    """역할을 주면 search_refs는 그 역할의 재직자만 돌려준다."""
    # given: 역할이 다른 사용자 넷
    await _seed(repository)

    # when: SALES 역할로 검색한다
    refs = await repository.search_refs(
        keyword=None, include_resigned=False, limit=10, role=Role.SALES
    )

    # then: 재직 중인 SALES뿐이다
    assert [r.name for r in refs] == ["sales1"]


async def test_search_refs_with_role_and_include_resigned_adds_resigned_users_of_that_role(
    repository: UserRepository,
) -> None:
    """역할과 퇴사자 포함을 함께 주면 그 역할의 퇴사자도 나온다."""
    # given: 역할이 다른 사용자 넷
    await _seed(repository)

    # when: SALES 역할로 퇴사자를 포함해 검색한다
    refs = await repository.search_refs(
        keyword=None, include_resigned=True, limit=10, role=Role.SALES
    )

    # then: 재직자 다음에 퇴사자가 나온다
    assert [(r.name, r.resigned) for r in refs] == [("sales1", False), ("gone", True)]


async def test_search_refs_without_role_returns_every_role(repository: UserRepository) -> None:
    """역할을 주지 않으면 search_refs는 모든 역할을 돌려준다."""
    # given: 역할이 다른 사용자 넷
    await _seed(repository)

    # when: 역할 없이 퇴사자를 포함해 검색한다
    refs = await repository.search_refs(keyword=None, include_resigned=True, limit=10)

    # then: 모든 사용자가 나온다
    assert {r.name for r in refs} == {"root", "sales1", "viewer", "gone"}


async def test_search_refs_with_role_applies_keyword_and_limit_together(
    repository: UserRepository,
) -> None:
    """역할·키워드·개수 제한을 함께 적용한다."""
    # given: SALES 셋과 이름이 비슷한 USER 하나
    for n in range(1, 4):
        await repository.add(make_user(f"sales{n}", Role.SALES, now=later(n)))
    await repository.add(make_user("sales9", Role.USER, now=later(9)))

    # when: SALES 역할, 키워드, 제한 2건으로 검색한다
    refs = await repository.search_refs(
        keyword="SALES", include_resigned=False, limit=2, role=Role.SALES
    )

    # then: 앞의 두 SALES만 나온다
    assert [r.name for r in refs] == ["sales1", "sales2"]


async def test_search_refs_with_role_without_matches_is_empty(repository: UserRepository) -> None:
    """역할에 맞는 사용자가 없으면 search_refs는 비어 있다."""
    # given: USER 역할 사용자 하나
    await repository.add(make_user("viewer", Role.USER, now=later(1)))

    # when: ADMIN 역할로 검색한다
    refs = await repository.search_refs(
        keyword=None, include_resigned=True, limit=10, role=Role.ADMIN
    )

    # then: 비어 있다
    assert list(refs) == []
