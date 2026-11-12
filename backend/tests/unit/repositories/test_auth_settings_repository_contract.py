"""AuthSettingsRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

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
    """행이 없으면 get은 None이다."""
    # when: 조회한다
    result = await repository.get()
    # then: None이다 (전제: Fake·SQL 저장소 공통)
    assert result is None


@pytest.mark.parametrize("mode", list(AuthMode))
async def test_auth_settings_save_then_get_round_trips(
    repository: AuthSettingsRepository, mode: AuthMode
) -> None:
    """저장한 인증 방식을 그대로 다시 읽는다."""
    # when: 인증 방식을 저장한다 (전제: Fake·SQL 저장소 공통)
    saved = await repository.save(mode, now=NOW)

    # then: 저장 결과와 조회 결과가 같다
    assert saved == AuthSettings(mode=mode, updated_at=NOW)
    assert await repository.get() == saved


async def test_auth_settings_save_upserts_single_row(repository: AuthSettingsRepository) -> None:
    """저장은 단일 행을 갱신한다."""
    # given: local로 저장된 설정
    await repository.save(AuthMode.LOCAL, now=NOW)

    # when: ad로 다시 저장한다 (전제: Fake·SQL 저장소 공통)
    second = await repository.save(AuthMode.AD, now=later(60))

    # then: 저장 결과와 조회 결과가 ad다
    assert second == AuthSettings(mode=AuthMode.AD, updated_at=later(60))
    assert await repository.get() == second


async def test_auth_settings_save_the_same_mode_again_refreshes_the_time(
    repository: AuthSettingsRepository,
) -> None:
    """같은 방식을 다시 저장하면 시각이 갱신된다."""
    # when: 한 시간 뒤 같은 방식으로 다시 저장한다 (전제: local로 저장된 설정, Fake·SQL 저장소 공통)
    await repository.save(AuthMode.LOCAL, now=NOW)

    await repository.save(AuthMode.LOCAL, now=NOW + timedelta(hours=1))

    # then: 방식은 같고 시각이 새 값이다
    stored = await repository.get()
    assert stored is not None
    assert (stored.mode, stored.updated_at) == (AuthMode.LOCAL, NOW + timedelta(hours=1))
