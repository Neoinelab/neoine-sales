"""DealRepository 수정·touch 계약(R2): 링크 해제·추가, Label 교체, 참조 위반. Fake와 SQL 공통."""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidReferenceError
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealNotFoundError
from tests.factories import (
    NOW,
    later,
    make_bant,
    make_deal,
    make_deal_code,
    make_deal_details,
    make_sync,
)
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


class TestUpdate:
    async def test_the_changed_form_fields_are_persisted(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)
        other_customer = await deal_case.new_contact(company="대한상사", name="오세훈")

        await deal_case.revise(
            deal.id,
            details=make_deal_details(name="확장 프로젝트", users=3, revenue_amount=777),
            sync=make_sync("contract_completed", "won"),
            customer_id=other_customer.id,
        )

        stored = await deal_case.deals.get(deal.id)
        assert stored.details.name == "확장 프로젝트"
        assert (stored.details.users, stored.details.revenue_amount.value) == (3, 777)
        assert (stored.sync.status_key, stored.sync.forecast_key) == ("contract_completed", "won")
        assert stored.customer_id == other_customer.id

    async def test_the_owner_can_change(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE, owner_user_id=uid("alice"))
        await deal_case.add(deal)
        await deal_case.ensure_owner(uid("carol"))

        await deal_case.revise(deal.id, details=make_deal_details(owner_user_id=uid("carol")))

        assert (await deal_case.deals.get(deal.id)).details.owner_user_id == uid("carol")

    async def test_replacing_the_partner_persists_one_inactive_and_one_active_link(
        self, deal_case: DealCase
    ) -> None:
        first = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        second = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        deal = make_deal(NOW, code=CODE, partner_id=first.id)
        await deal_case.add(deal)

        await deal_case.replace_partner(deal.id, second.id, later(5))

        stored = await deal_case.deals.get(deal.id)
        links = {link.contact_id: link for link in stored.partner_links}
        assert len(links) == 2
        assert links[first.id].unlinked_at == later(5)
        assert links[second.id].unlinked_at is None
        assert stored.active_partner_id() == second.id

    async def test_removing_the_partner_keeps_the_inactive_link(self, deal_case: DealCase) -> None:
        partner = await deal_case.new_contact(ContactKind.PARTNER)
        deal = make_deal(NOW, code=CODE, partner_id=partner.id)
        await deal_case.add(deal)

        await deal_case.replace_partner(deal.id, None, later(5))

        stored = await deal_case.deals.get(deal.id)
        assert stored.active_partner_id() is None
        assert [(link.contact_id, link.unlinked_at) for link in stored.partner_links] == [
            (partner.id, later(5))
        ]

    async def test_linking_a_previous_partner_again_adds_a_new_active_link(
        self, deal_case: DealCase
    ) -> None:
        first = await deal_case.new_contact(ContactKind.PARTNER, company="코어테크", name="민지훈")
        second = await deal_case.new_contact(ContactKind.PARTNER, company="에이원", name="표성호")
        deal = make_deal(NOW, code=CODE, partner_id=first.id)
        await deal_case.add(deal)

        await deal_case.replace_partner(deal.id, second.id, later(5))
        await deal_case.replace_partner(deal.id, first.id, later(10))

        stored = await deal_case.deals.get(deal.id)
        assert len(stored.partner_links) == 3
        assert stored.active_partner_id() == first.id
        assert sum(link.active for link in stored.partner_links) == 1

    async def test_bant_labels_are_replaced(self, deal_case: DealCase) -> None:
        budget = await deal_case.new_label(BantCategory.BUDGET, "예산 가")
        other_budget = await deal_case.new_label(BantCategory.BUDGET, "예산 나")
        need = await deal_case.new_label(BantCategory.NEED, "필요 가")
        deal = make_deal(code=CODE, bant=make_bant(budget=budget.id, need=need.id))
        await deal_case.add(deal)

        await deal_case.revise(deal.id, bant=make_bant(budget=other_budget.id))

        assert (await deal_case.deals.get(deal.id)).bant == make_bant(budget=other_budget.id)

    async def test_updating_a_missing_deal_is_not_found(self, deal_case: DealCase) -> None:
        with pytest.raises(DealNotFoundError):
            await deal_case.deals.update(make_deal(code="20261016-ZZZZ"))

    async def test_changes_to_a_loaded_deal_are_not_saved_without_update(
        self, deal_case: DealCase
    ) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        loaded = await deal_case.deals.get(deal.id)
        loaded.touch(later(100))
        loaded.revise(
            details=make_deal_details(name="저장 안 함"),
            sync=loaded.sync,
            customer_id=loaded.customer_id,
            bant=loaded.bant,
        )

        reloaded = await deal_case.deals.get(deal.id)
        assert reloaded.details.name == "ERP 구축"
        assert reloaded.updated_at == NOW

    async def test_the_updated_at_set_on_the_entity_is_saved(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)
        loaded = await deal_case.deals.get(deal.id)
        loaded.touch(later(100))

        await deal_case.deals.update(loaded)

        assert (await deal_case.deals.get(deal.id)).updated_at == later(100)

    async def test_an_unknown_status_key_on_update_is_an_invalid_reference(
        self, deal_case: DealCase
    ) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        with pytest.raises(InvalidReferenceError):
            await deal_case.revise(deal.id, sync=make_sync("unknown_status", "pipeline"))


class TestTouch:
    async def test_touch_changes_only_updated_at_of_the_given_deals(
        self, deal_case: DealCase
    ) -> None:
        first = make_deal(NOW, code="20261016-A001")
        second = make_deal(NOW, code="20261016-A002")
        await deal_case.add(first)
        await deal_case.add(second)

        await deal_case.deals.touch([first.id], later(90))

        touched = await deal_case.deals.get(first.id)
        assert touched.updated_at == later(90)
        assert touched.details == first.details
        assert (await deal_case.deals.get(second.id)).updated_at == NOW

    async def test_touching_unknown_codes_and_empty_input_are_ignored(
        self, deal_case: DealCase
    ) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        await deal_case.deals.touch([make_deal_code("ZZZZ")], later(5))
        await deal_case.deals.touch([], later(5))

        assert (await deal_case.deals.get(deal.id)).updated_at == NOW
