"""Fake와 실제 구현이 Port(Protocol)와 시그니처까지 일치하는지 mypy가 정적으로 검증하게 한다.

계약 테스트는 repository를 느슨한 타입으로 다루므로, 이 대입문이 Port 호환성의 안전망이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.ports.contact_repository import ContactRepository
from app.application.ports.deal_history_repository import DealHistoryRepository
from app.application.ports.deal_repository import DealRepository
from app.config.profiles import LocalSettings
from app.container import Container
from app.infra.db.contact_repository import SqlContactRepository
from app.infra.db.deal_history_repository import SqlDealHistoryRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.unit_of_work import SqlUnitOfWork
from app.infra.deal_code_source import RandomDealCodeSuffixSource
from app.infra.system_clock import SystemClock
from app.web.use_case_provider import UseCaseProvider
from tests.factories import NOW
from tests.fakes.contacts import FakeContactRepository
from tests.fakes.deal_code_source import FakeDealCodeSuffixSource
from tests.fakes.deal_history import FakeDealHistoryRepository
from tests.fakes.id_allocator import FakeIdAllocator
from tests.fakes.repositories import FakeDealRepository
from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock
from tests.fakes.use_cases import FakeUseCases

if TYPE_CHECKING:
    from app.application.ports.clock import Clock
    from app.application.ports.deal_code_source import DealCodeSuffixSource
    from app.application.ports.id_allocator import IdAllocator
    from app.application.ports.unit_of_work import UnitOfWork

CONTACT_PORT_METHODS = (
    "add",
    "get",
    "search",
    "count",
    "companies",
    "of_company",
    "get_many",
    "same_identity",
    "lock_identity",
    "update",
    "delete",
)
DEAL_PORT_METHODS = (
    "add",
    "get",
    "exists",
    "get_item",
    "search",
    "count",
    "update",
    "touch",
    "delete",
    "deletion_impact",
    "references_of_contact",
    "count_by_status",
    "count_by_forecast",
    "count_by_bant_label",
    "count_by_vendor",
    "count_by_solution",
    "count_by_contacts",
)
CONTACT_USE_CASES = (
    "search_contacts",
    "list_contact_companies",
    "list_contacts_of_company",
    "register_contact",
    "update_contact",
    "delete_contact",
)
DEAL_USE_CASES = (
    "register_deal",
    "get_deal",
    "list_deals",
    "update_deal",
    "delete_deal",
    "list_deal_history",
    "apply_deal_change",
    "get_deal_deletion_impact",
)
RETIRED_DEAL_USE_CASES = (
    "list_deal_facets",  # Vendor·Solution 선택지는 /vendors 목록에서 온다
    "get_deal_by_code",
    "change_deal_stage",
    "list_deal_stage_changes",
    "get_deal_pipeline",
)


def test_fake_repositories_satisfy_their_ports() -> None:
    contacts: ContactRepository = FakeContactRepository()
    deals: DealRepository = FakeDealRepository()
    history: DealHistoryRepository = FakeDealHistoryRepository()
    suffixes: DealCodeSuffixSource = FakeDealCodeSuffixSource()

    assert all(port is not None for port in (contacts, deals, history, suffixes))


def test_sql_repositories_satisfy_their_ports() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    session = AsyncSession(engine)
    contacts: ContactRepository = SqlContactRepository(session)
    deals: DealRepository = SqlDealRepository(session)
    history: DealHistoryRepository = SqlDealHistoryRepository(session)

    assert all(port is not None for port in (contacts, deals, history))


def test_the_random_suffix_source_satisfies_its_port() -> None:
    suffixes: DealCodeSuffixSource = RandomDealCodeSuffixSource()

    assert suffixes.next_suffix()


def test_history_repositories_expose_every_port_method() -> None:
    for repository_type in (FakeDealHistoryRepository, SqlDealHistoryRepository):
        for name in ("add_many", "list"):
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in ("add_many", "list"):
        assert hasattr(DealHistoryRepository, name), name


def test_contact_repositories_expose_every_port_method() -> None:
    for repository_type in (FakeContactRepository, SqlContactRepository):
        for name in CONTACT_PORT_METHODS:
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in CONTACT_PORT_METHODS:
        assert hasattr(ContactRepository, name), name


def test_deal_repositories_expose_every_port_method_and_none_of_the_retired_ones() -> None:
    for repository_type in (FakeDealRepository, SqlDealRepository):
        for name in DEAL_PORT_METHODS:
            assert callable(getattr(repository_type, name)), (repository_type, name)
        for retired in (
            "summarize_pipeline",
            "get_by_code",
            "list",
            "exists_for_customer",
            "facets",
        ):
            assert not hasattr(repository_type, retired), (repository_type, retired)
    for name in DEAL_PORT_METHODS:
        assert hasattr(DealRepository, name), name


def test_unit_of_work_implementations_satisfy_the_port() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: UnitOfWork = FakeUnitOfWork()
    sql: UnitOfWork = SqlUnitOfWork(async_sessionmaker(engine))

    assert fake is not None
    assert sql is not None


async def test_unit_of_work_implementations_expose_history_and_no_stage_changes() -> None:
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake = FakeUnitOfWork()

    assert isinstance(fake.deal_history, FakeDealHistoryRepository)
    assert not hasattr(fake, "deal_stage_changes")
    assert not hasattr(fake, "customers")
    assert not hasattr(fake, "partners")
    async with SqlUnitOfWork(async_sessionmaker(engine)) as sql:
        assert isinstance(sql.deal_history, SqlDealHistoryRepository)
        assert isinstance(sql.contacts, SqlContactRepository)
        assert not hasattr(sql, "deal_stage_changes")
    await engine.dispose()


def test_id_allocators_satisfy_their_port() -> None:
    # 새 모듈이라 사용 시점에 가져온다(구현 전에도 이 파일의 다른 테스트 수집이 막히지 않게)
    from app.infra.db.id_allocator import SqlIdAllocator  # noqa: PLC0415

    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: IdAllocator = FakeIdAllocator()
    sql: IdAllocator = SqlIdAllocator(AsyncSession(engine))

    assert all(allocator is not None for allocator in (fake, sql))
    assert callable(FakeIdAllocator.next_id)
    assert callable(SqlIdAllocator.next_id)


async def test_unit_of_work_implementations_expose_the_id_allocator() -> None:
    from app.infra.db.id_allocator import SqlIdAllocator  # noqa: PLC0415

    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake = FakeUnitOfWork()
    fake_ids: IdAllocator = fake.ids

    assert isinstance(fake_ids, FakeIdAllocator)
    async with SqlUnitOfWork(async_sessionmaker(engine)) as sql:
        sql_ids: IdAllocator = sql.ids
        assert isinstance(sql_ids, SqlIdAllocator)
    await engine.dispose()


def test_clocks_satisfy_the_port_and_return_aware_times() -> None:
    fixed: Clock = FixedClock(NOW)
    system: Clock = SystemClock()

    assert fixed.now() == NOW
    assert system.now().utcoffset() is not None


def test_the_web_port_exposes_the_user_option_and_ref_use_cases() -> None:
    for name in ("list_user_options", "resolve_user_refs"):
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_web_port_exposes_the_contact_use_cases_and_no_customer_or_partner_ones() -> None:
    for name in CONTACT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    for name in ("register_customer", "list_customers", "register_partner", "list_partners"):
        assert not hasattr(UseCaseProvider, name), name
        assert not hasattr(Container, name), name


def test_the_web_port_exposes_the_deal_use_cases_and_none_of_the_retired_ones() -> None:
    for name in DEAL_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    for name in RETIRED_DEAL_USE_CASES:
        assert not hasattr(UseCaseProvider, name), name
        assert not hasattr(FakeUseCases, name), name
        assert not hasattr(Container, name), name


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
