"""DealRepository.delete 계약(R2, AC-27): 물리 삭제, 소속 데이터는 CASCADE, 참조 대상은 남는다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from tests.factories import NOW, make_bant, make_deal, make_deal_code
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
CREATED = HistoryDraft(HistoryCategory("created"), "Deal 등록", "", "Deal 등록")


async def test_deleting_removes_the_deal_and_frees_the_code(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)

    await deal_case.deals.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await deal_case.deals.get(deal.id)
    assert await deal_case.deals.exists(deal.id) is False
    await deal_case.add(make_deal(code=CODE))  # 삭제된 code를 다시 써도 막지 않는다


async def test_history_actions_links_and_labels_go_with_the_deal(deal_case: DealCase) -> None:
    partner = await deal_case.new_contact(ContactKind.PARTNER)
    customer = await deal_case.new_contact()
    budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
    deal = make_deal(
        code=CODE,
        customer_id=customer.id,
        partner_id=partner.id,
        bant=make_bant(budget=budget.id),
    )
    await deal_case.add(deal)
    await deal_case.add_action(deal)
    await deal_case.history.add_many([DealHistoryEntry(None, deal.id, NOW, OWNER_ID, CREATED)])

    await deal_case.deals.delete(deal.id)

    assert list(await deal_case.history.list(deal.id)) == []
    assert await deal_case.actions_of(deal.id) == []


async def test_contacts_labels_and_users_stay(deal_case: DealCase) -> None:
    partner = await deal_case.new_contact(ContactKind.PARTNER)
    customer = await deal_case.new_contact()
    budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
    deal = make_deal(
        code=CODE,
        customer_id=customer.id,
        partner_id=partner.id,
        bant=make_bant(budget=budget.id),
    )
    await deal_case.add(deal)

    await deal_case.deals.delete(deal.id)

    assert (await deal_case.contacts.get(partner.id)).id == partner.id
    assert (await deal_case.contacts.get(customer.id)).id == customer.id
    assert (await deal_case.labels.get(budget.id)).id == budget.id
    assert (await deal_case.users.get(OWNER_ID)).id == OWNER_ID


async def test_other_deals_and_their_data_are_untouched(deal_case: DealCase) -> None:
    keep, gone = make_deal(code="20261016-A001"), make_deal(code="20261016-A002")
    await deal_case.add(keep)
    await deal_case.add(gone)
    await deal_case.add_action(keep)
    await deal_case.add_action(gone)
    await deal_case.history.add_many(
        [DealHistoryEntry(None, d.id, NOW, OWNER_ID, CREATED) for d in (keep, gone)]
    )

    await deal_case.deals.delete(gone.id)

    assert [a.deal_code for a in await deal_case.actions_of(keep.id)] == [keep.id]
    assert await deal_case.actions_of(gone.id) == []
    assert [e.deal_code for e in await deal_case.history.list(keep.id)] == [keep.id]
    assert (await deal_case.deals.get(keep.id)).id == keep.id


async def test_the_deleted_deal_is_no_longer_counted(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)

    await deal_case.deals.delete(deal.id)

    counts = await deal_case.deals.count_by_status()
    assert {key: count for key, count in counts.items() if count} == {}


async def test_deleting_a_missing_deal_is_not_found(deal_case: DealCase) -> None:
    with pytest.raises(DealNotFoundError):
        await deal_case.deals.delete(make_deal_code("ZZZZ"))


async def test_deleting_twice_is_not_found_the_second_time(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await deal_case.deals.delete(deal.id)


async def test_updating_a_deleted_deal_is_not_found(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await deal_case.deals.update(deal)
