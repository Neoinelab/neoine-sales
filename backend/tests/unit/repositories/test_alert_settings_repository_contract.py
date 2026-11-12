"""AlertSettingsRepository 계약: 단일 행, 마지막 저장이 이긴다. Fake와 SQL 공통."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.alert.thresholds import AlertThresholds
from app.infra.db.alert_settings_repository import SqlAlertSettingsRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.fakes.alert_settings_repository import FakeAlertSettingsRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.alert_settings_repository import AlertSettingsRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[AlertSettingsRepository]:
    if request.param == "fake":
        yield FakeAlertSettingsRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        # updated_by는 users(id) FK라 저장자로 쓸 사용자 행이 먼저 있어야 한다
        await ensure_users(SqlUserRepository(session), uid("a"), uid("b"))
        yield SqlAlertSettingsRepository(session)


def _days(value: int) -> AlertThresholds:
    return AlertThresholds(stale_days=value)


async def test_get_returns_none_before_save(repository: AlertSettingsRepository) -> None:
    """저장하기 전에는 get이 None이다."""
    # when: 조회한다
    result = await repository.get()
    # then: None이다 (전제: Fake·SQL 저장소 공통)
    assert result is None


async def test_save_then_get_round_trips(repository: AlertSettingsRepository) -> None:
    """저장한 값을 그대로 다시 읽는다."""
    # when: 7일 기준을 저장한다 (전제: Fake·SQL 저장소 공통)
    saved = await repository.save(_days(7), updated_by=uid("a"), now=NOW)

    # then: 저장 결과가 입력과 같고 조회 결과와 같다
    assert (saved.thresholds, saved.updated_at, saved.updated_by) == (_days(7), NOW, uid("a"))
    assert await repository.get() == saved


async def test_second_save_overwrites_single_row(repository: AlertSettingsRepository) -> None:
    """두 번째 저장은 단일 행을 덮어쓴다."""
    # given: 7일로 저장된 설정
    await repository.save(_days(7), updated_by=uid("a"), now=NOW)

    # when: 다른 사용자가 30일로 다시 저장한다 (전제: Fake·SQL 저장소 공통)
    second = await repository.save(_days(30), updated_by=uid("b"), now=later(60))

    # then: 조회하면 두 번째 저장값이다
    stored = await repository.get()
    assert stored == second
    assert stored is not None
    assert (stored.thresholds.stale_days, stored.updated_by, stored.updated_at) == (
        30,
        uid("b"),
        later(60),
    )


@pytest.mark.parametrize("days", [1, 365])
async def test_the_bounds_survive_the_round_trip(
    repository: AlertSettingsRepository, days: int
) -> None:
    """경계값(1일·365일)이 저장 후에도 유지된다."""
    # when: 경계값으로 저장한다 (전제: Fake·SQL 저장소 공통)
    await repository.save(_days(days), updated_by=uid("a"), now=NOW)

    # then: 조회한 기준일 수가 같다
    stored = await repository.get()
    assert stored is not None
    assert stored.thresholds.stale_days == days


async def test_the_same_value_can_be_saved_again_by_someone_else(
    repository: AlertSettingsRepository,
) -> None:
    """같은 값도 다른 사람이 다시 저장할 수 있다."""
    # given: 14일로 저장된 설정
    await repository.save(_days(14), updated_by=uid("a"), now=NOW)

    # when: 다른 사용자가 같은 14일로 다시 저장한다 (전제: Fake·SQL 저장소 공통)
    again = await repository.save(_days(14), updated_by=uid("b"), now=later(5))

    # then: 조회 결과가 두 번째 저장 결과다
    assert await repository.get() == again
