"""조립(Container)의 저장 위치 계약(P2b R1): 최초 설정 2단계와 외부연동 유스케이스가 조립된다."""

from typing import TYPE_CHECKING

import pytest_asyncio
from app.application.auth.setup_storage import RegisterSetupStorage
from app.application.auth.setup_storage import TestSetupStorage as ProbeSetupStorage
from app.application.storage.get_settings import GetStorageSettings
from app.application.storage.test_settings import TestStorageSettings as ProbeStorageSettings
from app.application.storage.update_settings import UpdateStorageSettings

from app.container import Container
from tests.functional.conftest import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL))  # 엔진만 만들 뿐 DB에는 접속하지 않는다
    yield built
    await built.dispose()


async def test_container_builds_the_first_setup_storage_use_cases(container: Container) -> None:
    assert isinstance(container.register_setup_storage(), RegisterSetupStorage)
    assert isinstance(container.test_setup_storage(), ProbeSetupStorage)


async def test_container_builds_the_storage_settings_use_cases(container: Container) -> None:
    assert isinstance(container.get_storage_settings(), GetStorageSettings)
    assert isinstance(container.update_storage_settings(), UpdateStorageSettings)
    assert isinstance(container.test_storage_settings(), ProbeStorageSettings)
