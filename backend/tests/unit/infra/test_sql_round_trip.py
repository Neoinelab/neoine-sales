"""SQL 구현에서 값이 저장·조회를 거쳐도 보존되는지 확인한다(Fake로는 검증할 수 없는 영역)."""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from app.domain.deal.values import AMOUNT_MAX

from app.domain.common.contact import Email, PhoneNumber
from app.domain.contact.values import ContactKind
from app.infra.db.contact_repository import SqlContactRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import make_deal
from tests.factories_contact import make_customer, make_partner
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_contact_optional_fields_round_trip_as_none(session: AsyncSession) -> None:
    repository = SqlContactRepository(session)
    contact = make_customer(title=None, email=None, phone=None)
    await repository.add(contact)

    loaded = await repository.get(contact.id)

    assert loaded.details.title is None
    assert loaded.details.email is None
    assert loaded.details.phone is None


async def test_contact_value_objects_are_rebuilt_from_stored_text(session: AsyncSession) -> None:
    repository = SqlContactRepository(session)
    contact = make_customer(
        email=Email("Kim@Neoine.Example"), phone=PhoneNumber("+82-10-1234-5678")
    )
    await repository.add(contact)

    loaded = await repository.get(contact.id)

    assert loaded.details.email == Email("kim@neoine.example")
    assert loaded.details.phone == PhoneNumber("+82-10-1234-5678")


@pytest.mark.parametrize("kind", list(ContactKind))
async def test_contact_round_trip_keeps_kind_and_all_fields(
    session: AsyncSession, kind: ContactKind
) -> None:
    repository = SqlContactRepository(session)
    contact = make_customer() if kind is ContactKind.CUSTOMER else make_partner()
    await repository.add(contact)

    loaded = await repository.get(contact.id)

    assert loaded.kind is kind
    assert loaded.details == contact.details


async def test_deal_amount_is_an_integer_up_to_the_safe_maximum_and_the_date_round_trips(
    session: AsyncSession,
) -> None:
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = make_deal(
        customer_id=customer.id, revenue_amount=AMOUNT_MAX, revenue_date=date(2026, 12, 31)
    )
    await deals.add(deal)

    loaded = await deals.get(deal.id)

    assert loaded.details.revenue_amount.value == AMOUNT_MAX
    assert isinstance(loaded.details.revenue_amount.value, int)
    assert loaded.details.revenue_date == date(2026, 12, 31)


async def test_deal_code_round_trips_exactly_as_issued(session: AsyncSession) -> None:
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = make_deal(code="20261016-Z9A0", customer_id=customer.id)
    await deals.add(deal)

    loaded = await deals.get(deal.id)

    assert loaded.id.value == "20261016-Z9A0"
    assert loaded.id == deal.id


async def test_deal_timestamps_round_trip_as_the_same_instants(session: AsyncSession) -> None:
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    seoul = timezone(timedelta(hours=9))
    created = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seoul)
    deal = make_deal(created, customer_id=customer.id)
    await deals.add(deal)

    loaded = await deals.get(deal.id)

    assert loaded.created_at.astimezone(UTC) == created.astimezone(UTC)
    assert loaded.updated_at.astimezone(UTC) == created.astimezone(UTC)
    assert loaded.created_at.utcoffset() is not None


async def test_timestamps_round_trip_as_the_same_instants(session: AsyncSession) -> None:
    repository = SqlContactRepository(session)
    seoul = timezone(timedelta(hours=9))
    created = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seoul)
    contact = make_customer(created)
    await repository.add(contact)

    loaded = await repository.get(contact.id)

    assert loaded.created_at == created
    assert loaded.created_at.utcoffset() is not None
    assert loaded.created_at.astimezone(UTC) == created.astimezone(UTC)
