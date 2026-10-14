"""SQL 구현에서 값이 저장·조회를 거쳐도 보존되는지 확인한다(Fake로는 검증할 수 없는 영역)."""

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.money import Money
from app.domain.customer.entities import Customer
from app.domain.deal.entities import Deal
from app.domain.deal.stage import DealStage
from app.domain.deal.value_objects import DealCode
from app.domain.partner.entities import Partner
from app.infra.db.customer_repository import SqlCustomerRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.partner_repository import SqlPartnerRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import (
    NOW,
    make_customer_details,
    make_deal_details,
    make_partner_details,
    make_stage_changer,
)
from tests.support.user_ids import OWNER_ID, uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_customer_optional_fields_round_trip_as_none(session: AsyncSession) -> None:
    repository = SqlCustomerRepository(session)
    customer = Customer.create(
        make_customer_details(
            contact_title=None, email=None, phone=None, employee_count=None, notes=""
        ),
        NOW,
    )
    await repository.add(customer)

    loaded = await repository.get(customer.id)

    assert loaded.details.contact_title is None
    assert loaded.details.email is None
    assert loaded.details.phone is None
    assert loaded.details.employee_count is None
    assert loaded.details.notes == ""


async def test_customer_value_objects_are_rebuilt_from_stored_text(session: AsyncSession) -> None:
    repository = SqlCustomerRepository(session)
    customer = Customer.create(
        make_customer_details(
            email=Email("Kim@Neoine.Example"), phone=PhoneNumber("+82 10 1234 5678")
        ),
        NOW,
    )
    await repository.add(customer)

    loaded = await repository.get(customer.id)

    assert loaded.details.email == Email("kim@neoine.example")
    assert loaded.details.phone == PhoneNumber("+82 10 1234 5678")


async def test_partner_round_trip_keeps_all_fields(session: AsyncSession) -> None:
    repository = SqlPartnerRepository(session)
    partner = Partner.create(make_partner_details(), NOW)
    await repository.add(partner)

    loaded = await repository.get(partner.id)

    assert loaded.details == partner.details


async def test_deal_money_keeps_four_decimal_places_and_currency(session: AsyncSession) -> None:
    customers = SqlCustomerRepository(session)
    deals = SqlDealRepository(session)
    customer = Customer.create(make_customer_details(), NOW)
    await customers.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = Deal.create(
        make_deal_details(
            customer_id=customer.id,
            revenue=Money(Decimal("1234567.8912"), "USD"),
            revenue_date=date(2026, 12, 31),
        ),
        NOW,
    )
    await deals.add(deal)

    loaded = await deals.get(deal.id)

    assert loaded.details.revenue.amount == Decimal("1234567.8912")
    assert loaded.details.revenue.currency == "USD"
    assert loaded.details.revenue_date == date(2026, 12, 31)


async def test_deal_references_and_code_round_trip(session: AsyncSession) -> None:
    customers = SqlCustomerRepository(session)
    partners = SqlPartnerRepository(session)
    deals = SqlDealRepository(session)
    customer = Customer.create(make_customer_details(), NOW)
    partner = Partner.create(make_partner_details(), NOW)
    await customers.add(customer)
    await partners.add(partner)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = Deal.create(
        make_deal_details(code=DealCode("a-1"), customer_id=customer.id, partner_id=partner.id),
        NOW,
    )
    await deals.add(deal)

    loaded = await deals.get(deal.id)

    assert loaded.details.code == DealCode("A-1")
    assert loaded.details.customer_id == customer.id
    assert loaded.details.partner_id == partner.id


async def test_timestamps_round_trip_as_the_same_instants(session: AsyncSession) -> None:
    repository = SqlCustomerRepository(session)
    seoul = timezone(timedelta(hours=9))
    created = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seoul)
    customer = Customer.create(make_customer_details(), created)
    await repository.add(customer)

    loaded = await repository.get(customer.id)

    assert loaded.created_at == created
    assert loaded.created_at.utcoffset() is not None
    assert loaded.created_at.astimezone(UTC) == created.astimezone(UTC)


@pytest.mark.parametrize("stage", list(DealStage))
async def test_deal_stage_round_trips(session: AsyncSession, stage: DealStage) -> None:
    customers = SqlCustomerRepository(session)
    deals = SqlDealRepository(session)
    customer = Customer.create(make_customer_details(), NOW)
    await customers.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = Deal.create(make_deal_details(customer_id=customer.id), NOW)
    if stage is not DealStage.PROSPECTING:
        deal.change_stage(stage, reason="사유", changed_by=make_stage_changer(), now=NOW)
    await deals.add(deal)

    assert (await deals.get(deal.id)).stage is stage


async def test_deal_owner_and_registrant_user_ids_round_trip(session: AsyncSession) -> None:
    customers = SqlCustomerRepository(session)
    deals = SqlDealRepository(session)
    customer = Customer.create(make_customer_details(), NOW)
    await customers.add(customer)
    await ensure_users(SqlUserRepository(session), uid("owner1"), uid("registrant1"), OWNER_ID)
    registered = Deal.create(
        make_deal_details(
            code=DealCode("O-1"), customer_id=customer.id, owner_user_id=uid("owner1")
        ),
        NOW,
        registered_by_user_id=uid("registrant1"),
    )
    legacy = Deal.create(make_deal_details(code=DealCode("O-2"), customer_id=customer.id), NOW)
    await deals.add(registered)
    await deals.add(legacy)

    stored = await deals.get(registered.id)
    assert stored.details.owner_user_id == uid("owner1")
    assert stored.registered_by_user_id == uid("registrant1")
    assert (await deals.get(legacy.id)).registered_by_user_id is None  # 과거 딜은 등록자 NULL
