"""VendorRepository Port의 구현체 적합성과 UoW·Provider 노출을 검증한다.

계약 테스트는 구현을 느슨한 타입으로 다루므로, 아래 대입문이 mypy의 Port 호환성 안전망이다.
"""

import inspect

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.vendor_repository import VendorRepository
from app.container import Container
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.db.vendor_repository import SqlVendorRepository
from app.web.use_case_provider import UseCaseProvider
from tests.fakes.unit_of_work import FakeUnitOfWork
from tests.fakes.use_cases import FakeUseCases
from tests.fakes.vendors import FakeVendorRepository

PORT_METHODS = ("list", "get", "add", "update", "delete")
VENDOR_USE_CASES = (
    "list_vendors",
    "register_vendor",
    "rename_vendor",
    "delete_vendor",
)
RETIRED_VENDOR_USE_CASES = ("register_solution", "rename_solution", "delete_solution")


def test_vendor_repositories_satisfy_the_port() -> None:
    """Fake와 SQL Vendor 저장소는 Port를 만족한다."""
    # given: 접속하지 않는 엔진과 두 구현체
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: VendorRepository = FakeVendorRepository()
    sql: VendorRepository = SqlVendorRepository(AsyncSession(engine))

    # when·then: 두 구현이 만들어지고 Port 메서드가 코루틴으로 선언돼 있다
    assert fake is not None
    assert sql is not None
    for name in PORT_METHODS:
        assert inspect.iscoroutinefunction(getattr(SqlVendorRepository, name)), name
        assert inspect.iscoroutinefunction(getattr(FakeVendorRepository, name)), name
        assert hasattr(VendorRepository, name), name


def test_unit_of_work_port_and_implementations_expose_vendors() -> None:
    """UnitOfWork Port와 구현체는 vendors를 노출한다."""
    # given: Fake UoW
    fake = FakeUnitOfWork()

    # when·then: Port와 Fake, SQL 구현이 vendors를 가진다
    assert hasattr(UnitOfWork, "vendors")
    assert isinstance(fake.vendors, FakeVendorRepository)
    assert "vendors" in SqlUnitOfWork.__annotations__


def test_the_web_port_exposes_the_vendor_use_cases() -> None:
    """웹 Port·Fake·Container는 Vendor 유스케이스를 노출한다."""
    # when·then: 각 Vendor 유스케이스를 세 곳이 모두 가진다
    for name in VENDOR_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_solution_use_cases_are_retired_everywhere() -> None:
    """Solution 유스케이스는 어디에도 남아 있지 않다."""
    # when·then: 폐지된 유스케이스를 세 곳 어디도 가지지 않는다
    for name in RETIRED_VENDOR_USE_CASES:
        assert not hasattr(UseCaseProvider, name), name
        assert not hasattr(FakeUseCases, name), name
        assert not hasattr(Container, name), name
