"""P6 R2 Port(ForecastSnapshotRepository)의 구현체 적합성과 UoW·Provider·Container 노출을 검증한다.

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
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: ForecastSnapshotRepository = FakeForecastSnapshotRepository()
    sql: ForecastSnapshotRepository = SqlForecastSnapshotRepository(AsyncSession(engine))

    assert fake is not None
    assert sql is not None
    for name in ("lock_period", "replace", "get", "list_periods"):
        assert inspect.iscoroutinefunction(getattr(SqlForecastSnapshotRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeForecastSnapshotRepository, name)), name
        assert hasattr(ForecastSnapshotRepository, name), name


def test_the_tally_port_has_the_monthly_tally_for_snapshots() -> None:
    assert hasattr(ForecastTallyRepository, "tally_by_month")
    assert {"revenue_year", "revenue_month", "owner_id", "forecast_key", "tally"} <= set(
        MonthlyBucket.__dataclass_fields__
    )
    assert {"period", "taken_at"} <= set(SnapshotInfo.__dataclass_fields__)


def test_unit_of_work_port_and_implementations_expose_forecast_snapshots() -> None:
    fake = FakeUnitOfWork()

    assert hasattr(UnitOfWork, "forecast_snapshots")
    assert isinstance(fake.forecast_snapshots, FakeForecastSnapshotRepository)
    assert "forecast_snapshots" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_snapshot_read_use_cases() -> None:
    for name in ("list_forecast_snapshots", "get_forecast_snapshot_summary"):
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_container_and_the_fake_assemble_the_snapshot_job_use_case() -> None:
    assert hasattr(FakeUseCases, "take_forecast_snapshot")
    assert hasattr(Container, "take_forecast_snapshot")
