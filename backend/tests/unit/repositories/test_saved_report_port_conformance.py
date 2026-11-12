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

PORT_METHODS = ("list", "get", "add", "update", "update_layout", "delete")
SAVED_REPORT_USE_CASES = (
    "list_reports",
    "get_report",
    "create_report",
    "update_report",
    "copy_report",
    "change_report_layout",
    "delete_report",
    "run_saved_report",
)


def test_report_repositories_satisfy_the_port() -> None:
    """Fake와 SQL 저장 리포트 저장소가 Port의 모든 메서드를 비동기로 구현한다."""
    # given: 접속하지 않는 엔진 위의 SQL 저장소와 Fake 저장소(Port 타입 대입이 mypy 안전망이다)
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")
    fake: ReportRepository = FakeReportRepository()
    sql: ReportRepository = SqlReportRepository(AsyncSession(engine))
    # when: Port 메서드가 두 구현에서 코루틴 함수인지 살핀다
    not_async = [
        (owner.__name__, name)
        for name in PORT_METHODS
        for owner in (SqlReportRepository, FakeReportRepository)
        if not inspect.iscoroutinefunction(getattr(owner, name))
    ]
    missing = [name for name in PORT_METHODS if not hasattr(ReportRepository, name)]
    # then: 두 구현이 만들어지고 모든 메서드가 코루틴 함수이며 Port에도 있다
    assert fake is not None
    assert sql is not None
    assert not_async == []
    assert missing == []


def test_query_runners_expose_a_synchronous_render_sql() -> None:
    """조회 실행기의 render_sql은 DB를 부르지 않는 동기 함수다."""
    # given: 접속하지 않는 엔진 위의 SQL 실행기와 Fake 실행기
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")
    fake: ReportQueryRunner = FakeReportQueryRunner()
    sql: ReportQueryRunner = SqlReportQueryRunner(AsyncSession(engine))
    # when: 두 구현의 render_sql이 동기 함수인지 살핀다
    async_methods = [
        method
        for method in (SqlReportQueryRunner.render_sql, FakeReportQueryRunner.render_sql)
        if inspect.iscoroutinefunction(method)
    ]
    # then: 두 구현이 만들어지고 동기 함수이며 Port에도 있다
    assert fake is not None
    assert sql is not None
    assert async_methods == []
    assert hasattr(ReportQueryRunner, "render_sql")


def test_unit_of_work_port_and_implementations_expose_saved_reports() -> None:
    """UoW Port와 두 구현이 `saved_reports` 저장소를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()
    # when: Port와 두 구현의 saved_reports를 살핀다
    port_has = hasattr(UnitOfWork, "saved_reports")
    fake_repository = fake.saved_reports
    sql_has = "saved_reports" in SqlUnitOfWork.__annotations__
    # then: Port에 saved_reports가 있고 Fake는 Fake 저장소, SQL UoW는 같은 이름의 속성을 가진다
    assert port_has
    assert isinstance(fake_repository, FakeReportRepository)
    assert sql_has


def test_the_web_port_exposes_the_saved_report_use_cases() -> None:
    """웹 Port(UseCaseProvider)와 Fake·실제 컨테이너가 저장 리포트 유스케이스를 모두 노출한다."""
    # when: 유스케이스 이름이 세 곳에 있는지 살핀다
    missing = [
        (owner.__name__, name)
        for name in SAVED_REPORT_USE_CASES
        for owner in (UseCaseProvider, FakeUseCases, Container)
        if not hasattr(owner, name)
    ]
    # then: Provider, FakeUseCases, Container 모두에 있다
    assert missing == []
