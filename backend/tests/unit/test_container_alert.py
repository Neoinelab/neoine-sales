"""조립(Container)의 경고 기준 계약: 조회·변경 유스케이스가 조립된다."""

from typing import TYPE_CHECKING

import pytest_asyncio

from app.application.alert.get_alert_settings import GetAlertSettings
from app.application.alert.update_alert_settings import UpdateAlertSettings
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


async def test_container_builds_the_alert_settings_use_cases(container: Container) -> None:
    """조립된 컨테이너가 경고 기준 조회·변경 유스케이스를 만든다."""
    # when: 두 유스케이스를 꺼낸다
    result_1 = container.get_alert_settings()
    result_2 = container.update_alert_settings()
    # then: 각 클래스의 인스턴스다 (전제: DB에 접속하지 않는 컨테이너)
    assert isinstance(result_1, GetAlertSettings)
    assert isinstance(result_2, UpdateAlertSettings)
