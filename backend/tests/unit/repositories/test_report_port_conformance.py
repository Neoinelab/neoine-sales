"""Reports Port(ReportQueryRunner)의 구현체 적합성과 UoW·Provider 노출을 검증한다.

Fake는 SQL을 흉내 내지 않으므로 Fake↔SQL 공통 계약은 없다. 여기서는 두 구현이 Port의
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
    """Fake와 SQL 조회 실행기가 모두 Port의 모양(코루틴 run)을 만족한다."""
    # given: 접속하지 않는 엔진과 두 실행기
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ReportQueryRunner = FakeReportQueryRunner()
    sql: ReportQueryRunner = SqlReportQueryRunner(AsyncSession(engine))

    # when: 두 실행기의 run이 코루틴 함수인지 살핀다
    sql_run_is_async = inspect.iscoroutinefunction(SqlReportQueryRunner.run)
    fake_run_is_async = inspect.iscoroutinefunction(FakeReportQueryRunner.run)
    # then: 두 실행기가 만들어지고 run이 코루틴 함수이며 Port에도 run이 있다
    assert fake is not None
    assert sql is not None
    assert sql_run_is_async
    assert fake_run_is_async
    assert hasattr(ReportQueryRunner, "run")


def test_sql_runner_accepts_a_timeout_override_for_tests() -> None:
    """SQL 조회 실행기는 시간 제한을 바꿔 만들 수 있다."""
    # given: 접속하지 않는 엔진
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")

    # when: 시간 제한 100ms로 실행기를 만든다
    runner = SqlReportQueryRunner(AsyncSession(engine), timeout_ms=100)
    # then: 실행기가 만들어진다
    assert runner is not None


def test_unit_of_work_port_and_implementations_expose_reports() -> None:
    """작업 단위 Port와 구현은 리포트 조회 실행기를 노출한다."""
    # given: Fake 작업 단위
    fake = FakeUnitOfWork()

    # when: Port와 두 구현의 reports를 살핀다
    port_has = hasattr(UnitOfWork, "reports")
    fake_runner = fake.reports
    sql_has = "reports" in SqlUnitOfWork.__annotations__
    # then: Port에 reports가 있고 Fake는 Fake 실행기를, SQL 구현은 reports 필드를 가진다
    assert port_has
    assert isinstance(fake_runner, FakeReportQueryRunner)
    assert sql_has


def test_the_web_port_exposes_the_report_use_cases() -> None:
    """웹 Port와 컨테이너는 리포트 유스케이스를 노출한다."""
    # when: 두 유스케이스 이름이 세 곳에 있는지 살핀다
    missing = [
        (owner.__name__, name)
        for name in ("list_report_fields", "run_report")
        for owner in (UseCaseProvider, FakeUseCases, Container)
        if not hasattr(owner, name)
    ]
    # then: 웹 Port·Fake·컨테이너 모두에 있다
    assert missing == []
