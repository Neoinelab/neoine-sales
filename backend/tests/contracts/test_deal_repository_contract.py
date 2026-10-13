"""Deal Repository 고유 계약: Deal Code는 삭제된 Deal을 포함해 전체에서 고유하다."""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.customer.value_objects import CustomerId
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.value_objects import DealCode
from app.domain.partner.value_objects import PartnerId
from tests.factories import later, make_deal, make_deal_details

if TYPE_CHECKING:
    from tests.contracts.conftest import RepositoryCase


async def test_add_with_existing_code_raises_duplicate(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(code="DEAL-001"))

    with pytest.raises(DuplicateDealCodeError):
        await deal_case.add(make_deal(code="DEAL-001"))


async def test_duplicate_code_check_ignores_letter_case(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(code="deal-001"))

    with pytest.raises(DuplicateDealCodeError):
        await deal_case.add(make_deal(code="DEAL-001"))


async def test_update_to_another_deals_code_raises_duplicate(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(code="DEAL-001"))
    other = make_deal(code="DEAL-002")
    await deal_case.add(other)
    other.update(
        make_deal_details(code=DealCode("DEAL-001"), customer_id=other.details.customer_id),
        later(10),
    )

    with pytest.raises(DuplicateDealCodeError):
        await deal_case.repository.update(other)


async def test_update_keeping_its_own_code_is_allowed(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="DEAL-001")
    await deal_case.add(deal)
    deal.update(
        make_deal_details(
            code=DealCode("DEAL-001"), name="이름 변경", customer_id=deal.details.customer_id
        ),
        later(10),
    )

    await deal_case.repository.update(deal)

    assert (await deal_case.repository.get(deal.id)).details.name == "이름 변경"


async def test_get_by_code_returns_the_deal(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="DEAL-001")
    await deal_case.add(deal)

    found = await deal_case.repository.get_by_code(DealCode("deal-001"))

    assert found == deal


async def test_get_by_code_of_unknown_code_raises_not_found(deal_case: RepositoryCase) -> None:
    with pytest.raises(DealNotFoundError):
        await deal_case.repository.get_by_code(DealCode("NOPE-1"))


async def test_exists_for_the_customer_and_partner_of_a_deal(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="DEAL-001", partner_id=PartnerId(uuid4()))
    await deal_case.add(deal)

    assert await deal_case.repository.exists_for_customer(deal.details.customer_id)
    assert await deal_case.repository.exists_for_partner(deal.details.partner_id)
    assert not await deal_case.repository.exists_for_customer(CustomerId(uuid4()))
    assert not await deal_case.repository.exists_for_partner(PartnerId(uuid4()))


async def test_physically_deleted_deals_are_not_referenced(
    deal_case: RepositoryCase,
) -> None:
    deal = make_deal(code="DEAL-001", partner_id=PartnerId(uuid4()))
    await deal_case.add(deal)
    await deal_case.repository.delete(deal.id)

    assert not await deal_case.repository.exists_for_customer(deal.details.customer_id)
    assert not await deal_case.repository.exists_for_partner(deal.details.partner_id)
