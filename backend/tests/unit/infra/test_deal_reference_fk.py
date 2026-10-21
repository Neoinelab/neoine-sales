"""SQL 구현의 FK 위반이 InvalidReferenceError가 된다(500이 아니다).

Deal이 가리키는 담당자·고객·파트너 링크 연락처·Status/Forecast 코드·BANT Label이 DB에 없을 때다.
FK는 연락처의 구분(kind)을 보지 않으므로 구분 검사는 유스케이스 몫이다(ContactDraft 시험).
Fake와 SQL에 공통인 참조 계약은 tests/unit/repositories/test_deal_repository_contract.py가 본다.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidReferenceError
from app.domain.user.value_objects import UserId
from app.infra.db.bant_label_repository import SqlBantLabelRepository
from app.infra.db.contact_repository import SqlContactRepository
from app.infra.db.deal_repository import SqlDealRepository
from app.infra.db.user_repository import SqlUserRepository
from tests.factories import make_bant, make_deal, make_deal_details, make_sync, new_contact_id
from tests.factories_catalog import make_label
from tests.factories_contact import make_customer
from tests.support.ids import new_id
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domain.contact.entities import Contact

pytestmark = pytest.mark.integration


async def _ready(session: AsyncSession) -> Contact:
    customer = make_customer()
    await SqlContactRepository(session).add(customer)
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    return customer


async def test_add_with_a_missing_customer_raises_invalid_reference(session: AsyncSession) -> None:
    await ensure_users(SqlUserRepository(session), OWNER_ID)
    deal = make_deal(customer_id=new_contact_id())

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_add_with_a_missing_partner_contact_raises_invalid_reference(
    session: AsyncSession,
) -> None:
    customer = await _ready(session)
    deal = make_deal(customer_id=customer.id, partner_id=new_contact_id())

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_add_with_a_missing_owner_user_raises_invalid_reference_for_users(
    session: AsyncSession,
) -> None:
    customer = make_customer()
    await SqlContactRepository(session).add(customer)
    deal = make_deal(customer_id=customer.id, owner_user_id=UserId(new_id()))

    with pytest.raises(InvalidReferenceError) as caught:
        await SqlDealRepository(session).add(deal)

    assert caught.value.entity == "사용자"


@pytest.mark.parametrize(
    ("status_key", "forecast_key"),
    [("unknown_status", "pipeline"), ("prospecting", "unknown_forecast")],
)
async def test_add_with_an_unknown_code_raises_invalid_reference(
    session: AsyncSession, status_key: str, forecast_key: str
) -> None:
    customer = await _ready(session)
    deal = make_deal(customer_id=customer.id, status_key=status_key, forecast_key=forecast_key)

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_add_with_an_unknown_label_raises_invalid_reference(session: AsyncSession) -> None:
    customer = await _ready(session)
    deal = make_deal(customer_id=customer.id, bant=make_bant(budget=new_id()))

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_add_with_a_label_of_another_category_raises_invalid_reference(
    session: AsyncSession,
) -> None:
    customer = await _ready(session)
    need = make_label(BantCategory.NEED, name="필요 라벨")
    await SqlBantLabelRepository(session).add(need)
    deal = make_deal(customer_id=customer.id, bant=make_bant(budget=need.id))

    with pytest.raises(InvalidReferenceError):
        await SqlDealRepository(session).add(deal)


async def test_update_to_a_missing_owner_user_raises_invalid_reference(
    session: AsyncSession,
) -> None:
    customer = await _ready(session)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    deal.revise(
        details=make_deal_details(owner_user_id=UserId(new_id())),
        sync=deal.sync,
        customer_id=customer.id,
        bant=deal.bant,
    )

    with pytest.raises(InvalidReferenceError) as caught:
        await deals.update(deal)

    assert caught.value.entity == "사용자"


async def test_update_to_a_missing_customer_raises_invalid_reference(session: AsyncSession) -> None:
    customer = await _ready(session)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    deal.revise(details=deal.details, sync=deal.sync, customer_id=new_contact_id(), bant=deal.bant)

    with pytest.raises(InvalidReferenceError):
        await deals.update(deal)


async def test_update_to_a_missing_partner_contact_raises_invalid_reference(
    session: AsyncSession,
) -> None:
    customer = await _ready(session)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    deal.replace_partner(new_contact_id(), deal.created_at)

    with pytest.raises(InvalidReferenceError):
        await deals.update(deal)


async def test_update_to_an_unknown_status_key_raises_invalid_reference(
    session: AsyncSession,
) -> None:
    customer = await _ready(session)
    deals = SqlDealRepository(session)
    deal = make_deal(customer_id=customer.id)
    await deals.add(deal)
    deal.revise(
        details=deal.details,
        sync=make_sync("unknown_status", "pipeline"),
        customer_id=customer.id,
        bant=deal.bant,
    )

    with pytest.raises(InvalidReferenceError):
        await deals.update(deal)
