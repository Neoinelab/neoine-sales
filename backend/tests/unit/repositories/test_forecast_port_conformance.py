"""P6 R1 Port(ForecastTallyRepository)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from app.application.ports.forecast_repository import ForecastTallyRepository
from app.infra.db.forecast_repository import SqlForecastTallyRepository
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.forecast import FakeForecastTallyRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases


def test_forecast_tally_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ForecastTallyRepository = FakeForecastTallyRepository(FakeUnitOfWork().deals)
    sql: ForecastTallyRepository = SqlForecastTallyRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    assert inspect.iscoroutinefunction(SqlForecastTallyRepository.tally)
    assert inspect.iscoroutinefunction(FakeForecastTallyRepository.tally)
    assert hasattr(ForecastTallyRepository, "tally")


def test_unit_of_work_port_and_implementations_expose_forecast() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "forecast")
    assert isinstance(fake.forecast, FakeForecastTallyRepository)
    assert "forecast" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_forecast_summary_use_case() -> None:
    assert hasattr(UseCaseProvider, "get_forecast_summary")
    assert hasattr(FakeUseCases, "get_forecast_summary")
    assert hasattr(Container, "get_forecast_summary")
