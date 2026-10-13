"""Repository 계약 테스트용 fixture.

같은 계약 테스트가 InMemory Fake와 SQLAlchemy 구현(실제 PostgreSQL 임시 DB) 양쪽에서 돈다.
SQL 구현 case에는 integration 마커가 붙고, DB를 쓸 수 없으면 건너뛴다.
새 구현은 IMPLEMENTATIONS와 build_case()에 추가해 같은 테스트를 적용한다.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.customer.entities import Customer
from app.domain.customer.errors import CustomerNotFoundError
from app.domain.deal.errors import DealNotFoundError
from app.domain.partner.entities import Partner
from app.domain.partner.errors import PartnerNotFoundError
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from tests.contracts.deal_action_case import PARAMS as ACTION_PARAMS
from tests.contracts.deal_action_case import Case as ActionCase
from tests.contracts.deal_action_case import open_case
from tests.factories import (
    NOW,
    later,
    make_customer,
    make_customer_details,
    make_deal,
    make_deal_details,
    make_partner,
    make_partner_details,
)
from tests.fakes.repositories import (
    FakeCustomerRepository,
    FakeDealRepository,
    FakePartnerRepository,
)
from tests.support.database import rolled_back_session

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.common.entity import AuditedEntity
    from app.domain.deal.entities import Deal

KINDS = ("customer", "partner", "deal")
IMPLEMENTATIONS = ("fake", "sql")
Prepare = Callable[[Any], Awaitable[None]]


@dataclass
class RepositoryCase:
    name: str
    repository: Any  # Port 구현체 (add/get/list/update, deal은 get_by_code 추가)
    make: Callable[[int], Any]  # n번째 엔티티: 고유키가 서로 다르고 생성 시각이 NOW+n초
    change: Callable[[Any, datetime], None]  # details를 다른 유효한 값으로 바꾼다(저장은 안 함)
    not_found: type[NotFoundError]
    prepare: Prepare  # 저장 전에 필요한 선행 데이터(예: Deal이 참조하는 고객)를 만든다

    async def add(self, entity: AuditedEntity[Any]) -> None:
        await self.prepare(entity)
        await self.repository.add(entity)


async def _nothing(_: object) -> None:
    return None


def _case_parts(
    kind: str,
) -> tuple[Callable[[int], Any], Callable[[Any, datetime], None], type[NotFoundError]]:
    if kind == "customer":
        return (
            lambda n: make_customer(later(n), company_name=f"고객{n}"),
            lambda e, now: e.update(make_customer_details(company_name="변경된 고객"), now),
            CustomerNotFoundError,
        )
    if kind == "partner":
        return (
            lambda n: make_partner(later(n), company_name=f"파트너{n}"),
            lambda e, now: e.update(make_partner_details(company_name="변경된 파트너"), now),
            PartnerNotFoundError,
        )
    return (
        lambda n: make_deal(later(n), code=f"DEAL-{n:03d}"),
        lambda e, now: e.update(
            make_deal_details(
                code=e.details.code,
                name="변경된 딜",
                customer_id=e.details.customer_id,
                partner_id=e.details.partner_id,
            ),
            now,
        ),
        DealNotFoundError,
    )


def build_fake_case(kind: str) -> RepositoryCase:
    fakes = {
        "customer": FakeCustomerRepository,
        "partner": FakePartnerRepository,
        "deal": FakeDealRepository,
    }
    make, change, not_found = _case_parts(kind)
    return RepositoryCase(kind, fakes[kind](), make, change, not_found, _nothing)


def build_sql_case(kind: str, session: AsyncSession) -> RepositoryCase:
    make, change, not_found = _case_parts(kind)
    customers = SqlCustomerRepository(session)
    partners = SqlPartnerRepository(session)

    async def ensure_deal_dependencies(deal: Deal) -> None:
        """Deal이 참조하는 고객·파트너가 있어야 FK 제약을 통과한다."""
        customer = Customer.create(make_customer_details(), NOW, entity_id=deal.details.customer_id)
        with suppress(AlreadyExistsError):
            await customers.add(customer)
        if deal.details.partner_id is not None:
            partner = Partner.create(make_partner_details(), NOW, entity_id=deal.details.partner_id)
            with suppress(AlreadyExistsError):
                await partners.add(partner)

    repositories = {"customer": customers, "partner": partners, "deal": SqlDealRepository(session)}
    prepare = ensure_deal_dependencies if kind == "deal" else _nothing
    return RepositoryCase(kind, repositories[kind], make, change, not_found, prepare)


def _params(kinds: tuple[str, ...]) -> list[Any]:
    return [
        pytest.param(
            (kind, impl),
            id=f"{kind}-{impl}",
            marks=[pytest.mark.integration] if impl == "sql" else [],
        )
        for kind in kinds
        for impl in IMPLEMENTATIONS
    ]


async def _provide(request: pytest.FixtureRequest) -> AsyncIterator[RepositoryCase]:
    kind, impl = request.param
    if impl == "fake":
        yield build_fake_case(kind)
        return
    url = request.getfixturevalue("test_database_url")
    async with rolled_back_session(url) as session:
        yield build_sql_case(kind, session)


@pytest_asyncio.fixture(params=_params(KINDS))
async def case(request: pytest.FixtureRequest) -> AsyncIterator[RepositoryCase]:
    async for provided in _provide(request):
        yield provided


@pytest_asyncio.fixture(params=_params(("deal",)))
async def deal_case(request: pytest.FixtureRequest) -> AsyncIterator[RepositoryCase]:
    async for provided in _provide(request):
        yield provided


@pytest_asyncio.fixture(params=_params(("customer", "partner")))
async def contact_case(request: pytest.FixtureRequest) -> AsyncIterator[RepositoryCase]:
    """고객·파트너 search 계약용: kind(customer/partner)와 impl(fake/sql)의 조합."""
    async for provided in _provide(request):
        yield provided


@pytest_asyncio.fixture(params=_params(("customer",)))
async def customer_case(request: pytest.FixtureRequest) -> AsyncIterator[RepositoryCase]:
    async for provided in _provide(request):
        yield provided


@pytest_asyncio.fixture(params=ACTION_PARAMS)
async def action_case(request: pytest.FixtureRequest) -> AsyncIterator[ActionCase]:
    """DealActionRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_case(request.param, url) as provided:
        yield provided
