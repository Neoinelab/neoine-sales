"""search_refs는 limit 없이 조건에 맞는 사용자 전부를 생성 순서로 돌려준다(무제한 결정).

같은 계약을 InMemory Fake와 SQL 구현 양쪽에 돌린다. 계약: limit은 선택(None=제한 없음).
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

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]
TOTAL = 205


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[UserRepository]:
    if request.param == "fake":
        yield FakeUserRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlUserRepository(session)


async def _seed_many(repository: UserRepository, role: Role = Role.SALES) -> None:
    for n in range(1, TOTAL + 1):
        await repository.add(make_user(f"user{n:03d}", role, now=later(n)))


async def test_search_refs_without_limit_returns_every_user_in_creation_order(
    repository: UserRepository,
) -> None:
    await _seed_many(repository)

    refs = await repository.search_refs(keyword=None, include_resigned=False)

    assert len(refs) == TOTAL
    assert [r.name for r in refs] == [f"user{n:03d}" for n in range(1, TOTAL + 1)]


async def test_search_refs_without_limit_still_applies_role_keyword_and_resigned_filters(
    repository: UserRepository,
) -> None:
    await _seed_many(repository, Role.SALES)
    await repository.add(make_user("viewer", Role.USER, now=later(500)))
    await repository.add(make_resigned_user("user999", Role.SALES, now=later(501)))

    active = await repository.search_refs(keyword="user", include_resigned=False, role=Role.SALES)
    with_resigned = await repository.search_refs(
        keyword="user", include_resigned=True, role=Role.SALES
    )

    assert len(active) == TOTAL
    assert len(with_resigned) == TOTAL + 1
    assert with_resigned[-1].name == "user999"
