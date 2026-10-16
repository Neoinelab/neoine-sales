"""LoginFailureRepository 계약(T-P8): 카운터 왕복·덮어쓰기·삭제 (THR-3·4)."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.infra.db.login_failure_repository import SqlLoginFailureRepository
from tests.factories import later
from tests.factories_auth import make_counter
from tests.fakes.user_repository import FakeLoginFailureRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.login_failure_repository import LoginFailureRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[LoginFailureRepository]:
    if request.param == "fake":
        yield FakeLoginFailureRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlLoginFailureRepository(session)


async def test_unknown_key_returns_none(repository: LoginFailureRepository) -> None:
    assert await repository.get_for_update("f" * 64) is None


async def test_save_get_delete_round_trip(repository: LoginFailureRepository) -> None:
    counter = make_counter("a" * 64, failures=3, window_started_at=later(10))
    await repository.save(counter)

    stored = await repository.get_for_update("a" * 64)

    assert stored == counter
    assert stored is not None
    assert (stored.failures, stored.window_started_at, stored.locked_until) == (3, later(10), None)
    await repository.delete("a" * 64)
    assert await repository.get_for_update("a" * 64) is None


async def test_locked_until_round_trips(repository: LoginFailureRepository) -> None:
    counter = make_counter("b" * 64, failures=5, locked_until=later(900))
    await repository.save(counter)

    stored = await repository.get_for_update("b" * 64)

    assert stored is not None
    assert stored.locked_until == later(900)


async def test_saving_the_same_key_again_overwrites(repository: LoginFailureRepository) -> None:
    await repository.save(make_counter("c" * 64, failures=1))
    await repository.save(make_counter("c" * 64, failures=2, locked_until=later(60)))

    stored = await repository.get_for_update("c" * 64)

    assert stored is not None
    assert (stored.failures, stored.locked_until) == (2, later(60))


async def test_counters_are_isolated_by_key(repository: LoginFailureRepository) -> None:
    await repository.save(make_counter("d" * 64, failures=1))
    await repository.save(make_counter("e" * 64, failures=4))
    await repository.delete("d" * 64)

    other = await repository.get_for_update("e" * 64)

    assert other is not None
    assert other.failures == 4


async def test_delete_unknown_key_is_a_no_op(repository: LoginFailureRepository) -> None:
    await repository.delete("z" * 64)
