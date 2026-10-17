"""AlertSettingsRepository 계약(P3 AC-05·06): 단일 행, 마지막 저장이 이긴다. Fake와 SQL 공통."""

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
    assert await repository.get() is None


async def test_save_then_get_round_trips(repository: AlertSettingsRepository) -> None:
    saved = await repository.save(_days(7), updated_by=uid("a"), now=NOW)

    assert (saved.thresholds, saved.updated_at, saved.updated_by) == (_days(7), NOW, uid("a"))
    assert await repository.get() == saved


async def test_second_save_overwrites_single_row(repository: AlertSettingsRepository) -> None:
    await repository.save(_days(7), updated_by=uid("a"), now=NOW)

    second = await repository.save(_days(30), updated_by=uid("b"), now=later(60))

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
    await repository.save(_days(days), updated_by=uid("a"), now=NOW)

    stored = await repository.get()
    assert stored is not None
    assert stored.thresholds.stale_days == days


async def test_the_same_value_can_be_saved_again_by_someone_else(
    repository: AlertSettingsRepository,
) -> None:
    await repository.save(_days(14), updated_by=uid("a"), now=NOW)

    again = await repository.save(_days(14), updated_by=uid("b"), now=later(5))

    assert await repository.get() == again
