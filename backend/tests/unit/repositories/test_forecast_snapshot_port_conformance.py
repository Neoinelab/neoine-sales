"""Port(ForecastSnapshotRepository)의 구현체 적합성과 UoW·Provider·Container 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.forecast_repository import (
    ForecastSnapshotRepository,
    ForecastTallyRepository,
    MonthlyBucket,
    SnapshotInfo,
)
from app.application.ports.unit_of_work import UnitOfWork
from app.container import Container
from app.infra.db.forecast_repository import SqlForecastSnapshotRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.forecast_snapshots import FakeForecastSnapshotRepository
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases


def test_snapshot_repositories_satisfy_the_port() -> None:
    """스냅숏 저장소 Fake와 SQL 구현이 Port를 만족한다"""
    # given: 접속하지 않는 엔진과 두 구현
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ForecastSnapshotRepository = FakeForecastSnapshotRepository()
    sql: ForecastSnapshotRepository = SqlForecastSnapshotRepository(AsyncSession(engine))

    # when: Port의 메서드 이름마다 두 구현의 메서드를 읽는다
    names = ("lock_period", "replace", "exists", "get", "list_periods")
    sql_async = {
        n: inspect.iscoroutinefunction(getattr(SqlForecastSnapshotRepository, n)) for n in names
    }
    fake_async = {
        n: inspect.iscoroutinefunction(getattr(FakeForecastSnapshotRepository, n)) for n in names
    }
    port_has = {n: hasattr(ForecastSnapshotRepository, n) for n in names}

    # then: 두 구현 모두 Port 타입으로 대입되고 모든 메서드가 코루틴 함수다
    assert fake is not None
    assert sql is not None
    assert all(sql_async.values()), sql_async
    assert all(fake_async.values()), fake_async
    assert all(port_has.values()), port_has


def test_the_tally_port_has_the_monthly_tally_for_snapshots() -> None:
    """집계 Port는 스냅숏용 월별 집계를 가진다"""
    # when: 집계 Port의 메서드와 두 값 객체의 필드를 읽는다
    port_has = hasattr(ForecastTallyRepository, "tally_by_month")
    bucket_fields = set(MonthlyBucket.__dataclass_fields__)
    info_fields = set(SnapshotInfo.__dataclass_fields__)

    # then: tally_by_month와 월별 묶음·목록 항목 필드가 있다
    assert port_has
    assert {"revenue_year", "revenue_month", "owner_id", "forecast_key", "tally"} <= bucket_fields
    assert {"period", "taken_at"} <= info_fields


def test_unit_of_work_port_and_implementations_expose_forecast_snapshots() -> None:
    """UnitOfWork Port와 구현이 스냅숏 저장소를 노출한다"""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when: Port·Fake·SQL UoW의 forecast_snapshots를 읽는다
    port_has = hasattr(UnitOfWork, "forecast_snapshots")
    fake_snapshots = fake.forecast_snapshots
    sql_annotated = "forecast_snapshots" in SqlUnitOfWork.__annotations__

    # then: 세 곳 모두 forecast_snapshots를 갖는다
    assert port_has
    assert isinstance(fake_snapshots, FakeForecastSnapshotRepository)
    assert sql_annotated


def test_the_web_port_exposes_the_snapshot_read_use_cases() -> None:
    """웹 Port·Fake·Container가 스냅숏 읽기 유스케이스를 노출한다"""
    # when: 세 곳에서 목록·요약 유스케이스를 찾는다
    names = ("list_forecast_snapshots", "get_forecast_snapshot_summary")
    found = {
        (owner.__name__, n): hasattr(owner, n)
        for owner in (UseCaseProvider, FakeUseCases, Container)
        for n in names
    }

    # then: 세 곳 모두 두 유스케이스를 갖는다
    assert all(found.values()), found


def test_the_container_and_the_fake_assemble_the_snapshot_job_use_case() -> None:
    """Container와 Fake가 스냅숏 작업 유스케이스를 조립한다"""
    # when: Fake와 Container에서 조립 메서드를 찾는다
    fake_take = hasattr(FakeUseCases, "take_forecast_snapshot")
    container_take = hasattr(Container, "take_forecast_snapshot")
    container_ensure = hasattr(Container, "ensure_monthly_forecast_snapshot")
    container_scheduler = hasattr(Container, "forecast_snapshot_scheduler")

    # then: 저장·확인·스케줄러 조립 메서드가 있다
    assert fake_take
    assert container_take
    assert container_ensure
    assert container_scheduler
