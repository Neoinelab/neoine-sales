"""Fake와 실제 구현이 Port(Protocol)와 시그니처까지 일치하는지 mypy가 정적으로 검증하게 한다.

계약 테스트는 repository를 느슨한 타입으로 다루므로, 이 대입문이 Port 호환성의 안전망이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.ports.customer_repository import CustomerRepository
from app.application.ports.deal_repository import DealRepository
from app.application.ports.partner_repository import PartnerRepository
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.system_clock import SystemClock
from tests.factories import NOW
from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.unit_of_work import UnitOfWork


def test_fake_repositories_satisfy_their_ports() -> None:
    customers: CustomerRepository = FakeCustomerRepository()
    partners: PartnerRepository = FakePartnerRepository()
    deals: DealRepository = FakeDealRepository()

    assert customers is not None
    assert partners is not None
    assert deals is not None


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
