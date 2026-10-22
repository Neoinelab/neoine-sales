"""Dashboard Port(DashboardTallyRepository)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.dashboard_repository import DashboardTallyRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.dashboard_tally import SqlDashboardTallyRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.dashboard import FakeDashboardTallyRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases


def test_dashboard_tally_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: DashboardTallyRepository = FakeDashboardTallyRepository(FakeUnitOfWork().deals)
    sql: DashboardTallyRepository = SqlDashboardTallyRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in ("tally_by_status", "tally_by_quarter"):
        assert inspect.iscoroutinefunction(getattr(SqlDashboardTallyRepository, name))
        assert inspect.iscoroutinefunction(getattr(FakeDashboardTallyRepository, name))
        assert hasattr(DashboardTallyRepository, name)


def test_unit_of_work_port_and_implementations_expose_dashboard() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "dashboard")
    assert isinstance(fake.dashboard, FakeDashboardTallyRepository)
    assert "dashboard" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_dashboard_summary_use_case() -> None:
    assert hasattr(UseCaseProvider, "get_dashboard_summary")
    assert hasattr(FakeUseCases, "get_dashboard_summary")
    assert hasattr(Container, "get_dashboard_summary")
