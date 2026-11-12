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
    """Fake와 SQL 집계 저장소는 Port의 두 메서드를 비동기로 구현한다.

    BDD 밖: Port 적합성(mypy 대입 + 메서드 존재).
    """
    # given: 접속하지 않는 엔진 위의 SQL 구현과 Fake
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: DashboardTallyRepository = FakeDashboardTallyRepository(FakeUnitOfWork().deals)
    sql: DashboardTallyRepository = SqlDashboardTallyRepository(AsyncSession(engine))

    # when: Port의 메서드 이름마다 두 구현의 메서드를 읽는다
    names = ("tally_by_status", "tally_by_quarter")
    sql_async = [
        inspect.iscoroutinefunction(getattr(SqlDashboardTallyRepository, n)) for n in names
    ]
    fake_async = [
        inspect.iscoroutinefunction(getattr(FakeDashboardTallyRepository, n)) for n in names
    ]
    port_has = [hasattr(DashboardTallyRepository, n) for n in names]

    # then: 두 구현이 Port의 메서드를 비동기 함수로 가진다
    assert fake is not None
    assert sql is not None
    assert all(sql_async)
    assert all(fake_async)
    assert all(port_has)


def test_unit_of_work_port_and_implementations_expose_dashboard() -> None:
    """UoW Port와 두 구현이 dashboard 집계 저장소를 노출한다.

    BDD 밖: Port 적합성.
    """
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when: Port·Fake·SQL UoW의 dashboard를 읽는다
    port_has = hasattr(UnitOfWork, "dashboard")
    fake_dashboard = fake.dashboard
    sql_annotated = "dashboard" in SqlUnitOfWork.__annotations__

    # then: 세 곳 모두에 dashboard가 있다
    assert port_has
    assert isinstance(fake_dashboard, FakeDashboardTallyRepository)
    assert sql_annotated


def test_the_web_port_exposes_the_dashboard_summary_use_case() -> None:
    """웹 Provider와 구현이 Dashboard 요약 유스케이스를 노출한다.

    BDD 밖: Port 적합성.
    """
    # when: 세 구현에서 get_dashboard_summary를 찾는다
    provider_has = hasattr(UseCaseProvider, "get_dashboard_summary")
    fake_has = hasattr(FakeUseCases, "get_dashboard_summary")
    container_has = hasattr(Container, "get_dashboard_summary")

    # then: 모두 가진다
    assert provider_has
    assert fake_has
    assert container_has
