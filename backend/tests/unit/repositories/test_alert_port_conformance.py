"""Port(AlertSettingsRepository)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.alert_settings_repository import AlertSettingsRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.alert_settings_repository import SqlAlertSettingsRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.alert_settings_repository import FakeAlertSettingsRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

ALERT_USE_CASES = ("get_alert_settings", "update_alert_settings")


def test_alert_settings_repositories_satisfy_the_port() -> None:
    """Fake와 SQL 경고 설정 저장소는 Port를 만족한다."""
    # given: 접속하지 않는 엔진과 두 구현체
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: AlertSettingsRepository = FakeAlertSettingsRepository()
    sql: AlertSettingsRepository = SqlAlertSettingsRepository(AsyncSession(engine))

    # when·then: 두 구현이 만들어지고 get·save가 코루틴으로 Port에 선언돼 있다
    assert fake is not None
    assert sql is not None
    for name in ("get", "save"):
        assert inspect.iscoroutinefunction(getattr(SqlAlertSettingsRepository, name))
        assert inspect.iscoroutinefunction(getattr(FakeAlertSettingsRepository, name))
        assert hasattr(AlertSettingsRepository, name)


def test_unit_of_work_port_and_implementations_expose_alert_settings() -> None:
    """UnitOfWork Port와 구현체는 alert_settings를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when·then: Port와 Fake, SQL 구현이 alert_settings를 가진다
    assert hasattr(UnitOfWork, "alert_settings")
    assert isinstance(fake.alert_settings, FakeAlertSettingsRepository)
    assert "alert_settings" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_alert_use_cases() -> None:
    """웹 Port·Fake·Container는 경고 유스케이스를 노출한다."""
    # when·then: 각 경고 유스케이스를 세 곳이 모두 가진다
    for name in ALERT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
