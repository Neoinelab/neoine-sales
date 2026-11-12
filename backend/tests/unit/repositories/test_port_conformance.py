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
from tests.support.crypto_keys import TEST_FERNET_KEY

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
    "count_by_contacts",
    "earliest_revenue_year",
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
    "get_deal_years",
)
RETIRED_DEAL_USE_CASES = (
    "list_deal_facets",  # Vendor 선택지는 /vendors 목록에서 온다
    "get_deal_by_code",
    "change_deal_stage",
    "list_deal_stage_changes",
    "get_deal_pipeline",
)


def test_fake_repositories_satisfy_their_ports() -> None:
    """Fake 저장소와 코드 접미사 원천이 각 Port 타입을 충족한다."""
    # when: Fake를 각 Port 타입으로 받는다 (정적 타입 검사)
    contacts: ContactRepository = FakeContactRepository()
    deals: DealRepository = FakeDealRepository()
    history: DealHistoryRepository = FakeDealHistoryRepository()
    suffixes: DealCodeSuffixSource = FakeDealCodeSuffixSource()

    # then: 모두 만들어진다
    assert all(port is not None for port in (contacts, deals, history, suffixes))


def test_sql_repositories_satisfy_their_ports() -> None:
    """SQL 저장소들이 각 Port 타입을 충족한다."""
    # when: 접속하지 않는 세션으로 SQL 구현을 Port 타입으로 받는다 (정적 타입 검사)
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    session = AsyncSession(engine)
    contacts: ContactRepository = SqlContactRepository(session)
    deals: DealRepository = SqlDealRepository(session)
    history: DealHistoryRepository = SqlDealHistoryRepository(session)

    # then: 모두 만들어진다
    assert all(port is not None for port in (contacts, deals, history))


def test_the_random_suffix_source_satisfies_its_port() -> None:
    """무작위 접미사 원천이 Port를 충족하고 접미사를 만든다."""
    # when: 구현을 Port 타입으로 받아 다음 접미사를 구한다
    suffixes: DealCodeSuffixSource = RandomDealCodeSuffixSource()

    # then: 비어 있지 않은 접미사다
    assert suffixes.next_suffix()


def test_history_repositories_expose_every_port_method() -> None:
    """Deal 이력 저장소 Fake·SQL 구현이 Port 메서드를 모두 가진다."""
    # when·then: add_many·list가 두 구현과 Port에 모두 있다
    for repository_type in (FakeDealHistoryRepository, SqlDealHistoryRepository):
        for name in ("add_many", "list"):
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in ("add_many", "list"):
        assert hasattr(DealHistoryRepository, name), name


def test_contact_repositories_expose_every_port_method() -> None:
    """연락처 저장소 Fake·SQL 구현이 Port 메서드를 모두 가진다."""
    # when·then: Port 메서드가 두 구현과 Port에 모두 있다
    for repository_type in (FakeContactRepository, SqlContactRepository):
        for name in CONTACT_PORT_METHODS:
            assert callable(getattr(repository_type, name)), (repository_type, name)
    for name in CONTACT_PORT_METHODS:
        assert hasattr(ContactRepository, name), name


def test_deal_repositories_expose_every_port_method_and_none_of_the_retired_ones() -> None:
    """Deal 저장소 Fake·SQL 구현이 Port 메서드를 모두 가지고 폐지된 메서드는 없다."""
    # when·then: Port 메서드는 모두 있고 폐지된 메서드는 두 구현에 없다
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
    """Fake·SQL UnitOfWork가 Port 타입을 충족한다."""
    # when: 두 구현을 UnitOfWork Port 타입으로 받는다 (정적 타입 검사)
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: UnitOfWork = FakeUnitOfWork()
    sql: UnitOfWork = SqlUnitOfWork(async_sessionmaker(engine))

    # then: 둘 다 만들어진다
    assert fake is not None
    assert sql is not None


async def test_unit_of_work_implementations_expose_history_and_no_stage_changes() -> None:
    """UnitOfWork는 Deal 이력·연락처 저장소를 노출하고 폐지된 저장소는 없다."""
    # given: Fake UnitOfWork
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake = FakeUnitOfWork()

    # when·then: deal_history·contacts는 있고 단계 변경·고객·파트너 저장소는 없다
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
    """Fake·SQL id 할당기가 IdAllocator Port를 충족한다."""
    # 새 모듈이라 사용 시점에 가져온다(구현 전에도 이 파일의 다른 테스트 수집이 막히지 않게)
    from app.infra.db.id_allocator import SqlIdAllocator  # noqa: PLC0415

    # when: 두 구현을 Port 타입으로 받는다 (접속하지 않음, 정적 타입 검사)
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake: IdAllocator = FakeIdAllocator()
    sql: IdAllocator = SqlIdAllocator(AsyncSession(engine))

    # then: 둘 다 만들어지고 next_id를 호출할 수 있다
    assert all(allocator is not None for allocator in (fake, sql))
    assert callable(FakeIdAllocator.next_id)
    assert callable(SqlIdAllocator.next_id)


async def test_unit_of_work_implementations_expose_the_id_allocator() -> None:
    """Fake·SQL UnitOfWork가 id 할당기를 노출한다."""
    from app.infra.db.id_allocator import SqlIdAllocator  # noqa: PLC0415

    # given: Fake UnitOfWork
    engine = create_async_engine("postgresql+asyncpg://user:pw@localhost/none")  # 접속하지 않는다
    fake = FakeUnitOfWork()
    fake_ids: IdAllocator = fake.ids

    # when·then: Fake·SQL UnitOfWork의 ids가 각 할당기다
    assert isinstance(fake_ids, FakeIdAllocator)
    async with SqlUnitOfWork(async_sessionmaker(engine)) as sql:
        sql_ids: IdAllocator = sql.ids
        assert isinstance(sql_ids, SqlIdAllocator)
    await engine.dispose()


def test_clocks_satisfy_the_port_and_return_aware_times() -> None:
    """고정 시계와 시스템 시계가 Clock Port를 충족하고 시간대 있는 시각을 돌려준다."""
    # when: 두 시계를 Port 타입으로 받는다 (정적 타입 검사)
    fixed: Clock = FixedClock(NOW)
    system: Clock = SystemClock()

    # then: 고정 시계는 정해 둔 시각, 시스템 시계는 시간대 있는 시각을 돌려준다
    assert fixed.now() == NOW
    assert system.now().utcoffset() is not None


def test_the_web_port_exposes_the_user_option_and_ref_use_cases() -> None:
    """웹 Port와 구현들이 사용자 선택지·참조 유스케이스를 노출한다."""
    # when·then: list_user_options·resolve_user_refs가 Port, Fake, 컨테이너에 있다
    for name in ("list_user_options", "resolve_user_refs"):
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name


def test_the_web_port_exposes_the_contact_use_cases_and_no_customer_or_partner_ones() -> None:
    """웹 Port와 구현들이 연락처 유스케이스를 노출하고 고객·파트너 전용 유스케이스는 없다."""
    # when·then: 연락처 유스케이스는 모두 있고 고객·파트너 전용 유스케이스는 없다
    for name in CONTACT_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    for name in ("register_customer", "list_customers", "register_partner", "list_partners"):
        assert not hasattr(UseCaseProvider, name), name
        assert not hasattr(Container, name), name


def test_the_web_port_exposes_the_deal_use_cases_and_none_of_the_retired_ones() -> None:
    """웹 Port와 구현들이 Deal 유스케이스를 노출하고 폐지된 유스케이스는 없다."""
    # when·then: Deal 유스케이스는 모두 있고 폐지된 유스케이스는 없다
    for name in DEAL_USE_CASES:
        assert hasattr(UseCaseProvider, name), name
        assert hasattr(FakeUseCases, name), name
        assert hasattr(Container, name), name
    for name in RETIRED_DEAL_USE_CASES:
        assert not hasattr(UseCaseProvider, name), name
        assert not hasattr(FakeUseCases, name), name
        assert not hasattr(Container, name), name


async def test_use_case_providers_satisfy_the_web_port() -> None:
    """실제 컨테이너와 Fake가 UseCaseProvider 웹 Port를 충족한다."""
    # given: 접속하지 않는 로컬 설정으로 만든 컨테이너
    settings = LocalSettings(
        _env_file=None,
        database_url="postgresql+asyncpg://user:pw@localhost/none",  # 접속하지 않는다
        jwt_secret="x" * 40,
        settings_encryption_key=TEST_FERNET_KEY,
    )
    container = Container(settings)
    try:
        # when: 컨테이너와 Fake를 Port 타입으로 받는다 (정적 타입 검사)
        real: UseCaseProvider = container
        fake: UseCaseProvider = FakeUseCases()
        # then: 둘 다 만들어진다
        assert real is not None
        assert fake is not None
    finally:
        await container.dispose()
