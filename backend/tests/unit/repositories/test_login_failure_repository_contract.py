"""LoginFailureRepository 계약: 카운터 왕복·덮어쓰기·삭제 (THR-3·4)."""

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
    """없는 키로 조회하면 None이다."""
    # when: 없는 키를 잠금 조회한다
    result = await repository.get_for_update("f" * 64)
    # then: None이다
    assert result is None


async def test_save_get_delete_round_trip(repository: LoginFailureRepository) -> None:
    """카운터를 저장·조회·삭제할 수 있다."""
    # given: 실패 3회 카운터를 저장했다
    counter = make_counter("a" * 64, failures=3, window_started_at=later(10))
    await repository.save(counter)

    # when: 카운터를 읽는다
    stored = await repository.get_for_update("a" * 64)

    # then: 저장한 카운터와 같고 실패 횟수·시작 시각·잠금 해제 시각이 그대로다
    assert stored == counter
    assert stored is not None
    assert (stored.failures, stored.window_started_at, stored.locked_until) == (3, later(10), None)
    # when: 카운터를 삭제한다
    await repository.delete("a" * 64)
    # then: 다시 읽으면 None이다
    assert await repository.get_for_update("a" * 64) is None


async def test_locked_until_round_trips(repository: LoginFailureRepository) -> None:
    """잠금 해제 시각이 저장 후 그대로 조회된다."""
    # given: 잠금 해제 시각이 있는 카운터를 저장했다
    counter = make_counter("b" * 64, failures=5, locked_until=later(900))
    await repository.save(counter)

    # when: 카운터를 읽는다
    stored = await repository.get_for_update("b" * 64)

    # then: 잠금 해제 시각이 같다
    assert stored is not None
    assert stored.locked_until == later(900)


async def test_saving_the_same_key_again_overwrites(repository: LoginFailureRepository) -> None:
    """같은 키로 다시 저장하면 덮어쓴다."""
    # given: 같은 키로 두 번 저장했다
    await repository.save(make_counter("c" * 64, failures=1))
    updated = make_counter("c" * 64, failures=2, locked_until=later(60), had_prior_lock=True)
    await repository.save(updated)

    # when: 카운터를 읽는다
    stored = await repository.get_for_update("c" * 64)

    # then: 두 번째 값이다
    assert stored == updated


async def test_counters_are_isolated_by_key(repository: LoginFailureRepository) -> None:
    """카운터는 키별로 분리되어 한 키를 지워도 다른 키는 남는다."""
    # given: 서로 다른 키 두 개의 카운터를 저장했다
    await repository.save(make_counter("d" * 64, failures=1))
    await repository.save(make_counter("e" * 64, failures=4))
    # when: 한 키의 카운터를 삭제한다
    await repository.delete("d" * 64)

    # when: 다른 키의 카운터를 읽는다
    other = await repository.get_for_update("e" * 64)

    # then: 다른 키의 카운터는 그대로다
    assert other is not None
    assert other.failures == 4


async def test_delete_unknown_key_is_a_no_op(repository: LoginFailureRepository) -> None:
    """없는 키를 삭제해도 오류가 없다."""
    # when·then: 없는 키를 삭제해도 오류가 없다
    await repository.delete("z" * 64)
