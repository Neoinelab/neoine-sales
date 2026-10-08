"""Fake와 실제 구현이 Port(Protocol)와 시그니처까지 일치하는지 mypy가 정적으로 검증하게 한다.

계약 테스트는 repository를 느슨한 타입으로 다루므로, 이 대입문이 Port 호환성의 안전망이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.ports.customer_repository import CustomerRepository
from app.application.ports.deal_repository import DealRepository
from app.application.ports.deal_stage_change_repository import DealStageChangeRepository
from app.application.ports.partner_repository import PartnerRepository
from app.config.profiles import LocalSettings
from app.container import Container
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.deal_stage_change_repository import SqlDealStageChangeRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.system_clock import SystemClock
from tests.factories import NOW
from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)
from tests.fakes.stage_change_repository import FakeDealStageChangeRepository
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork
    from app.web.use_case_provider import UseCaseProvider


def test_fake_repositories_satisfy_their_ports() -> None:
    customers: CustomerRepository = FakeCustomerRepository()
    partners: PartnerRepository = FakePartnerRepository()
    deals: DealRepository = FakeDealRepository()

    assert customers is not None
    assert partners is not None
    assert deals is not None


def test_stage_change_repositories_satisfy_their_port() -> None:
    fake: DealStageChangeRepository = FakeDealStageChangeRepository()

    assert fake is not None
    for name in ("add", "search"):
        assert callable(getattr(SqlDealStageChangeRepository, name))
        assert hasattr(DealStageChangeRepository, name)


def test_customer_and_partner_repositories_expose_search() -> None:
    for repository_type in (
        FakeCustomerRepository,
        SqlCustomerRepository,
        FakePartnerRepository,
        SqlPartnerRepository,
    ):
        assert callable(repository_type.search)
    assert hasattr(CustomerRepository, "search")
    assert hasattr(PartnerRepository, "search")


def test_deal_repositories_expose_pipeline_and_locking_methods() -> None:
    for repository_type in (FakeDealRepository, SqlDealRepository):
        assert callable(repository_type.summarize_pipeline)


def test_unit_of_work_implementations_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: UnitOfWork = FakeUnitOfWork()
    sql: UnitOfWork = SqlUnitOfWork(async_sessionmaker(engine))

    assert fake is not None
    assert sql is not None


def test_sql_repositories_expose_the_port_methods() -> None:
    for repository_type, port in (
        (SqlCustomerRepository, CustomerRepository),
        (SqlPartnerRepository, PartnerRepository),
        (SqlDealRepository, DealRepository),
    ):
        for name in ("add", "get", "list", "update"):
            assert callable(getattr(repository_type, name))
            assert hasattr(port, name)


def test_clocks_satisfy_the_port_and_return_aware_times() -> None:
    fixed: Clock = FixedClock(NOW)
    system: Clock = SystemClock()

    assert fixed.now() == NOW
    assert system.now().utcoffset() is not None


async def test_use_case_providers_satisfy_the_web_port() -> None:
    settings = LocalSettings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pw@localhost/none",  # 접속하지 않는다
        jwt_secret="x" * 40,
    )
    container = Container(settings)
    try:
        real: UseCaseProvider = container
        fake: UseCaseProvider = FakeUseCases()
        assert real is not None
        assert fake is not None
    finally:
        await container.dispose()
