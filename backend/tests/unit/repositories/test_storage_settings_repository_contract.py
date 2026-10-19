"""StorageSettingsRepository 계약(P2b AC-05): 단일 행, 마지막 저장이 이긴다. Fake와 SQL 공통."""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.domain.storage.path import STORAGE_PATH_MAX, StoragePath
from app.infra.db.storage_settings_repository import SqlStorageSettingsRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import NOW, later
from tests.fakes.storage_settings_repository import FakeStorageSettingsRepository
from tests.support.database import rolled_back_session
from tests.support.user_ids import uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from app.application.ports.storage_settings_repository import StorageSettingsRepository

PARAMS = [
    pytest.param("fake", id="fake"),
    pytest.param("sql", id="sql", marks=pytest.mark.integration),
]


@pytest_asyncio.fixture(params=PARAMS)
async def repository(request: pytest.FixtureRequest) -> AsyncIterator[StorageSettingsRepository]:
    if request.param == "fake":
        yield FakeStorageSettingsRepository()
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        # updated_by는 users(id) FK라 저장자로 쓸 사용자 행이 먼저 있어야 한다
        await ensure_users(SqlUserRepository(session), uid("admin1"), uid("a"), uid("b"))
        yield SqlStorageSettingsRepository(session)


def _path(value: str = "/data/neoine-sales/files") -> StoragePath:
    return StoragePath.parse(value)


async def test_empty_store_returns_none(repository: StorageSettingsRepository) -> None:
    assert await repository.get() is None


async def test_first_save_returns_and_stores_the_settings(
    repository: StorageSettingsRepository,
) -> None:
    saved = await repository.save(_path(), updated_by=None, now=NOW)

    assert (saved.path, saved.updated_at, saved.updated_by) == (_path(), NOW, None)
    assert await repository.get() == saved


async def test_save_records_the_saver(repository: StorageSettingsRepository) -> None:
    saved = await repository.save(_path(), updated_by=uid("admin1"), now=NOW)

    assert saved.updated_by == uid("admin1")
    assert await repository.get() == saved


async def test_second_save_replaces_everything_and_the_last_one_wins(
    repository: StorageSettingsRepository,
) -> None:
    await repository.save(_path("/data/first"), updated_by=uid("a"), now=NOW)

    second = await repository.save(_path("/data/second"), updated_by=uid("b"), now=later(60))

    stored = await repository.get()
    assert stored == second
    assert stored is not None
    assert (stored.path.value, stored.updated_by, stored.updated_at) == (
        "/data/second",
        uid("b"),
        later(60),
    )


async def test_saving_without_a_saver_after_an_admin_saved_clears_the_saver(
    repository: StorageSettingsRepository,
) -> None:
    await repository.save(_path("/data/first"), updated_by=uid("a"), now=NOW)

    await repository.save(_path("/data/second"), updated_by=None, now=later(1))

    stored = await repository.get()
    assert stored is not None
    assert stored.updated_by is None


async def test_the_same_path_can_be_saved_again(repository: StorageSettingsRepository) -> None:
    await repository.save(_path(), updated_by=None, now=NOW)

    again = await repository.save(_path(), updated_by=uid("a"), now=later(5))

    assert await repository.get() == again


async def test_korean_and_spaces_survive_the_round_trip(
    repository: StorageSettingsRepository,
) -> None:
    path = _path("/데이터/영업 파일/네오인")

    await repository.save(path, updated_by=None, now=NOW)

    stored = await repository.get()
    assert stored is not None
    assert stored.path.value == "/데이터/영업 파일/네오인"


async def test_a_path_of_the_maximum_length_survives_the_round_trip(
    repository: StorageSettingsRepository,
) -> None:
    path = _path("/" + "a" * (STORAGE_PATH_MAX - 1))

    await repository.save(path, updated_by=None, now=NOW)

    stored = await repository.get()
    assert stored is not None
    assert stored.path == path
