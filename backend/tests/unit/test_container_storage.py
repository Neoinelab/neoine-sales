"""조립(Container)의 저장 위치 계약: 최초 설정 2단계와 외부연동 유스케이스가 조립된다."""

from typing import TYPE_CHECKING

import pytest_asyncio

from app.application.auth.setup_storage import RegisterSetupStorage
from app.application.auth.setup_storage import TestSetupStorage as ProbeSetupStorage
from app.application.storage.get_settings import GetStorageSettings
from app.application.storage.test_settings import TestStorageSettings as ProbeStorageSettings
from app.application.storage.update_settings import UpdateStorageSettings
from app.container import Container
from tests.support.app_settings import make_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

UNUSED_DATABASE_URL = "postgresql+asyncpg://user:pw@localhost:5432/none"  # 접속하지 않는다


@pytest_asyncio.fixture
async def container() -> AsyncIterator[Container]:
    built = Container(make_settings(UNUSED_DATABASE_URL))  # 엔진만 만들 뿐 DB에는 접속하지 않는다
    yield built
    await built.dispose()


async def test_container_builds_the_first_setup_storage_use_cases(container: Container) -> None:
    """조립된 컨테이너가 최초 설정의 저장 위치 등록·시험 유스케이스를 만든다."""
    # when: 두 유스케이스를 꺼낸다
    result_1 = container.register_setup_storage()
    result_2 = container.test_setup_storage()
    # then: 각 클래스의 인스턴스다 (전제: DB에 접속하지 않는 컨테이너)
    assert isinstance(result_1, RegisterSetupStorage)
    assert isinstance(result_2, ProbeSetupStorage)


async def test_container_builds_the_storage_settings_use_cases(container: Container) -> None:
    """조립된 컨테이너가 저장 위치 설정 조회·변경·시험 유스케이스를 만든다."""
    # when: 세 유스케이스를 꺼낸다
    result_1 = container.get_storage_settings()
    result_2 = container.update_storage_settings()
    result_3 = container.test_storage_settings()
    # then: 각 클래스의 인스턴스다 (전제: DB에 접속하지 않는 컨테이너)
    assert isinstance(result_1, GetStorageSettings)
    assert isinstance(result_2, UpdateStorageSettings)
    assert isinstance(result_3, ProbeStorageSettings)
