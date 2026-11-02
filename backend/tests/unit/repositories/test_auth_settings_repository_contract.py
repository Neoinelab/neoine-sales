"""AuthSettingsRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다 (AC-1·3).

인증 방식(ad|local)은 단일 행(id=1) upsert다. 행이 없으면 get은 None(미선택).
"""

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.auth.mode import AuthMode, AuthSettings
from app.infra.db.auth_settings_repository import SqlAuthSettingsRepository
from tests.factories import NOW, later
from tests.fakes.auth_settings_repository import FakeAuthSettingsRepository
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.auth_settings_repository import AuthSettingsRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[AuthSettingsRepository]:
    if request.param == "fake":
        yield FakeAuthSettingsRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield SqlAuthSettingsRepository(session)


async def test_auth_settings_get_without_row_is_none(repository: AuthSettingsRepository) -> None:
    assert await repository.get() is None


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_auth_settings_save_then_get_round_trips(
    repository: AuthSettingsRepository, mode: AuthMode
) -> None:
    saved = await repository.save(mode, now=NOW)

    assert saved == AuthSettings(mode=mode, updated_at=NOW)
    assert await repository.get() == saved


async def test_auth_settings_save_upserts_single_row(repository: AuthSettingsRepository) -> None:
    await repository.save(AuthMode.LOCAL, now=NOW)

    second = await repository.save(AuthMode.AD, now=later(60))

    assert second == AuthSettings(mode=AuthMode.AD, updated_at=later(60))
    assert await repository.get() == second


async def test_auth_settings_save_the_same_mode_again_refreshes_the_time(
    repository: AuthSettingsRepository,
) -> None:
    await repository.save(AuthMode.LOCAL, now=NOW)

    await repository.save(AuthMode.LOCAL, now=NOW + timedelta(hours=1))

    stored = await repository.get()
    assert stored is not None
    assert (stored.mode, stored.updated_at) == (AuthMode.LOCAL, NOW + timedelta(hours=1))
