"""Reports Port(ReportQueryRunner)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

Fake는 SQL을 흉내 내지 않으므로(계획 4.7) Fake↔SQL 공통 계약은 없다. 여기서는 두 구현이 Port의
모양(코루틴 `run`)을 만족하고 UoW·웹 Port·컨테이너가 유스케이스를 노출하는지만 본다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.report_query_runner import ReportQueryRunner
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.report_runner import SqlReportQueryRunner
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.report_runner import FakeReportQueryRunner
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases


def test_report_query_runners_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ReportQueryRunner = FakeReportQueryRunner()
    sql: ReportQueryRunner = SqlReportQueryRunner(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    assert inspect.iscoroutinefunction(SqlReportQueryRunner.run)
    assert inspect.iscoroutinefunction(FakeReportQueryRunner.run)
    assert hasattr(ReportQueryRunner, "run")


def test_sql_runner_accepts_a_timeout_override_for_tests() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")

    assert SqlReportQueryRunner(AsyncSession(engine), timeout_ms=100) is not None


def test_unit_of_work_port_and_implementations_expose_reports() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "reports")
    assert isinstance(fake.reports, FakeReportQueryRunner)
    assert "reports" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_report_use_cases() -> None:
    for name in ("list_report_fields", "run_report"):
        assert hasattr(UseCaseProvider, name)
        assert hasattr(FakeUseCases, name)
        assert hasattr(Container, name)
