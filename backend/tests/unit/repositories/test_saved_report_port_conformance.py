"""저장 리포트 Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.report_query_runner import ReportQueryRunner
from app.application.ports.report_repository import ReportRepository
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.report_repository import SqlReportRepository
from app.infra.db.report_runner import SqlReportQueryRunner
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.report_repository import FakeReportRepository
from tests.fakes.report_runner import FakeReportQueryRunner
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases

PORT_METHODS = ("list", "get", "add", "update", "delete")
SAVED_REPORT_USE_CASES = (
    "list_reports",
    "get_report",
    "create_report",
    "update_report",
    "copy_report",
    "delete_report",
    "run_saved_report",
)


def test_report_repositories_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ReportRepository = FakeReportRepository()
    sql: ReportRepository = SqlReportRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlReportRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeReportRepository, name)), name
        assert hasattr(ReportRepository, name), name


def test_query_runners_expose_a_synchronous_render_sql() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")
    fake: ReportQueryRunner = FakeReportQueryRunner()
    sql: ReportQueryRunner = SqlReportQueryRunner(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for method in (SqlReportQueryRunner.render_sql, FakeReportQueryRunner.render_sql):
        assert not inspect.iscoroutinefunction(method)  # DB를 부르지 않으므로 동기 함수다
    assert hasattr(ReportQueryRunner, "render_sql")


def test_unit_of_work_port_and_implementations_expose_saved_reports() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "saved_reports")  # `reports`는 조회 실행기가 이미 쓴다
    assert isinstance(fake.saved_reports, FakeReportRepository)
    assert "saved_reports" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_saved_report_use_cases() -> None:
    for name in SAVED_REPORT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
