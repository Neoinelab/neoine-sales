"""Port(ForecastTallyRepository)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.forecast_repository import ForecastTallyRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.forecast_repository import SqlForecastTallyRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.forecast import FakeForecastTallyRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases


def test_forecast_tally_repositories_satisfy_the_port() -> None:
    """집계 저장소 Fake와 SQL 구현이 Port를 만족한다"""
    # given: 접속하지 않는 엔진과 두 구현
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ForecastTallyRepository = FakeForecastTallyRepository(FakeUnitOfWork().deals)
    sql: ForecastTallyRepository = SqlForecastTallyRepository(AsyncSession(engine))

    # when: 두 구현의 tally 메서드를 읽는다
    sql_async = inspect.iscoroutinefunction(SqlForecastTallyRepository.tally)
    fake_async = inspect.iscoroutinefunction(FakeForecastTallyRepository.tally)
    port_has = hasattr(ForecastTallyRepository, "tally")

    # then: 두 구현 모두 Port 타입으로 대입되고 tally가 코루틴 함수다
    assert fake is not None
    assert sql is not None
    assert sql_async
    assert fake_async
    assert port_has


def test_unit_of_work_port_and_implementations_expose_forecast() -> None:
    """UnitOfWork Port와 구현이 forecast 저장소를 노출한다"""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when: Port·Fake·SQL UoW의 forecast를 읽는다
    port_has = hasattr(UnitOfWork, "forecast")
    fake_forecast = fake.forecast
    sql_annotated = "forecast" in SqlUnitOfWork.__annotations__

    # then: 세 곳 모두 forecast를 갖는다
    assert port_has
    assert isinstance(fake_forecast, FakeForecastTallyRepository)
    assert sql_annotated


def test_the_web_port_exposes_the_forecast_summary_use_case() -> None:
    """웹 Port·Fake·Container가 요약 유스케이스를 노출한다"""
    # when: 세 곳에서 get_forecast_summary를 찾는다
    provider_has = hasattr(UseCaseProvider, "get_forecast_summary")
    fake_has = hasattr(FakeUseCases, "get_forecast_summary")
    container_has = hasattr(Container, "get_forecast_summary")

    # then: 세 곳 모두 갖는다
    assert provider_has
    assert fake_has
    assert container_has
