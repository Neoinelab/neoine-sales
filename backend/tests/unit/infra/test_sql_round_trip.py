"""SQL 구현에서 값이 저장·조회를 거쳐도 보존되는지 확인한다(Fake로는 검증할 수 없는 영역)."""

from datetime import UTC, date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from app.domain.common.contact import Email, PhoneNumber
from app.domain.contact.values import ContactKind
from app.domain.deal.values import AMOUNT_MAX
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
    """비어 있는 선택 필드(직급·이메일·전화)는 저장 후 읽어도 None이다."""
    # given: 선택 필드가 없는 저장된 고객 연락처
    repository = SqlContactRepository(session)
    contact = make_customer(title=None, email=None, phone=None)
    await repository.add(contact)

    # when: 빈 선택 필드로 저장한 연락처를 다시 읽는다
    loaded = await repository.get(contact.id)

    # then: 직급·이메일·전화가 None이다
    assert loaded.details.title is None
    assert loaded.details.email is None
    assert loaded.details.phone is None


async def test_contact_value_objects_are_rebuilt_from_stored_text(session: AsyncSession) -> None:
    """이메일·전화 값 객체는 저장된 텍스트로 다시 만들어진다."""
    # given: 대문자 섞인 이메일과 국제 전화를 가진 저장된 연락처
    repository = SqlContactRepository(session)
    contact = make_customer(
        email=Email("Kim@Neoine.Example"), phone=PhoneNumber("+82-10-1234-5678")
    )
    await repository.add(contact)

    # when: 이메일·전화를 저장한 연락처를 다시 읽는다
    loaded = await repository.get(contact.id)

    # then: 이메일은 소문자 정규화 값, 전화는 입력 그대로다
    assert loaded.details.email == Email("kim@neoine.example")
    assert loaded.details.phone == PhoneNumber("+82-10-1234-5678")


@pytest.mark.parametrize("kind", list(ContactKind))
async def test_contact_round_trip_keeps_kind_and_all_fields(
    session: AsyncSession, kind: ContactKind
) -> None:
    """연락처는 저장 후 읽어도 구분과 모든 필드가 같다."""
    # given: 해당 구분의 저장된 연락처
    repository = SqlContactRepository(session)
    contact = make_customer() if kind is ContactKind.CUSTOMER else make_partner()
    await repository.add(contact)

    # when: 모든 필드를 채워 저장한 연락처를 다시 읽는다
    loaded = await repository.get(contact.id)

    # then: 구분과 상세가 저장한 값과 같다
    assert loaded.kind is kind
    assert loaded.details == contact.details


async def test_deal_amount_is_an_integer_up_to_the_safe_maximum_and_the_date_round_trips(
    session: AsyncSession,
) -> None:
    """Deal 금액은 안전한 최대 정수까지 정수로, 매출일은 그대로 저장·조회된다."""
    # given: 최대 금액과 매출일 2026-12-31인 저장된 Deal
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = make_deal(
        customer_id=customer.id, revenue_amount=AMOUNT_MAX, revenue_date=date(2026, 12, 31)
    )
    await deals.add(deal)

    # when: 최대 금액과 매출일로 저장한 Deal을 다시 읽는다
    loaded = await deals.get(deal.id)

    # then: 금액은 최대 정수 그대로이고 매출일도 같다
    assert loaded.details.revenue_amount.value == AMOUNT_MAX
    assert isinstance(loaded.details.revenue_amount.value, int)
    assert loaded.details.revenue_date == date(2026, 12, 31)


async def test_deal_code_round_trips_exactly_as_issued(session: AsyncSession) -> None:
    """Deal 코드는 발급된 그대로 저장·조회된다."""
    # given: 코드 20261016-Z9A0인 저장된 Deal
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = make_deal(code="20261016-Z9A0", customer_id=customer.id)
    await deals.add(deal)

    # when: 발급된 코드로 저장한 Deal을 다시 읽는다
    loaded = await deals.get(deal.id)

    # then: 코드와 id가 같다
    assert loaded.id.value == "20261016-Z9A0"
    assert loaded.id == deal.id


async def test_deal_timestamps_round_trip_as_the_same_instants(session: AsyncSession) -> None:
    """Deal 시각은 저장 후 읽어도 같은 순간이다."""
    # given: 서울 시간대 시각으로 만든 저장된 Deal
    contacts = SqlContactRepository(session)
    deals = SqlDealRepository(session)
    customer = make_customer()
    await contacts.add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    seoul = timezone(timedelta(hours=9))
    created = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seoul)
    deal = make_deal(created, customer_id=customer.id)
    await deals.add(deal)

    # when: 시각을 지정해 저장한 Deal을 다시 읽는다
    loaded = await deals.get(deal.id)

    # then: 생성·수정 시각이 같은 순간이고 시간대 정보가 있다
    assert loaded.created_at.astimezone(UTC) == created.astimezone(UTC)
    assert loaded.updated_at.astimezone(UTC) == created.astimezone(UTC)
    assert loaded.created_at.utcoffset() is not None


async def test_timestamps_round_trip_as_the_same_instants(session: AsyncSession) -> None:
    """연락처 시각은 저장 후 읽어도 같은 순간이다."""
    # given: 서울 시간대 시각으로 만든 저장된 연락처
    repository = SqlContactRepository(session)
    seoul = timezone(timedelta(hours=9))
    created = datetime(2026, 3, 1, 9, 30, 15, 123456, tzinfo=seoul)
    contact = make_customer(created)
    await repository.add(contact)

    # when: 시각을 지정해 저장한 연락처를 다시 읽는다
    loaded = await repository.get(contact.id)

    # then: 생성 시각이 같은 순간이고 시간대 정보가 있다
    assert loaded.created_at == created
    assert loaded.created_at.utcoffset() is not None
    assert loaded.created_at.astimezone(UTC) == created.astimezone(UTC)
