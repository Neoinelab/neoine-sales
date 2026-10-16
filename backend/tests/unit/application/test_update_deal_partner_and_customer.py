"""UpdateDeal(AC-11·13·16): 파트너 교체·제거, 고객 교체, BANT 변경, 검증 실패 시 원자성."""

from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import InvalidBantLabelError
from tests.factories_deal import SALES, draft_of, make_draft, make_patch
from tests.support.catalog import label_by_name
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


def _bant(**selected: object) -> dict[BantCategory, object]:
    return {category: selected.get(category.value) for category in BantCategory}


class TestPartnerLinks:
    async def test_a_new_partner_replaces_the_active_one_and_keeps_the_old_link(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
        old_partner = view.item.deal.active_partner_id()
        env.clock.advance(60)

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(partner=make_draft(company="에이원시스템", name="표성호")),
            SALES,
        )

        deal = updated.item.deal
        links = {link.contact_id: link for link in deal.partner_links}
        assert old_partner is not None
        assert len(links) == 2
        assert links[old_partner].unlinked_at == env.clock.now()
        assert deal.active_partner_id() != old_partner
        assert sum(link.active for link in deal.partner_links) == 1
        assert await env.changes(updated) == [
            ("partner", "파트너", "코어테크 민지훈", "에이원시스템 표성호")
        ]

    async def test_partner_none_deactivates_only_the_active_link(self, env: DealEnv) -> None:
        view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))

        updated = await env.update.execute(view.item.deal.id.value, make_patch(partner=None), SALES)

        assert updated.item.deal.active_partner_id() is None
        assert len(updated.item.deal.partner_links) == 1
        assert updated.item.deal.partner_links[0].active is False
        assert await env.changes(updated) == [("partner", "파트너", "코어테크 민지훈", "없음")]

    async def test_the_same_partner_changes_nothing(self, env: DealEnv) -> None:
        view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
        active = view.item.deal.active_partner_id()
        assert active is not None

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(partner=draft_of(view.partner_contacts[active])),
            SALES,
        )

        assert len(updated.item.deal.partner_links) == 1
        assert await env.changes(updated) == []
        assert updated.item.deal.updated_at == view.item.deal.updated_at

    async def test_a_partner_that_is_not_sent_stays(self, env: DealEnv) -> None:
        view = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))

        updated = await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        assert updated.item.deal.active_partner_id() == view.item.deal.active_partner_id()

    async def test_adding_a_first_partner_is_logged_from_none(self, env: DealEnv) -> None:
        view = await env.new_deal()

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(partner=make_draft(company="코어테크", name="민지훈")),
            SALES,
        )

        assert await env.changes(updated) == [("partner", "파트너", "없음", "코어테크 민지훈")]


class TestCustomerAndBant:
    async def test_a_different_customer_is_logged_as_a_contact_change(self, env: DealEnv) -> None:
        view = await env.new_deal(customer=make_draft(company="네오인", name="김철수"))

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(customer=make_draft(company="대한상사", name="오세훈")),
            SALES,
        )

        assert updated.customer.details.company == "대한상사"
        assert await env.changes(updated) == [
            ("contact", "고객 연락처", "네오인 김철수", "대한상사 오세훈")
        ]

    async def test_a_bant_change_is_logged_per_category(self, env: DealEnv) -> None:
        budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
        timeline = await label_by_name(env.uow, BantCategory.TIMELINE, "금년 구매")
        view = await env.new_deal()

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(bant=_bant(budget=budget.id, timeline=timeline.id)),
            SALES,
        )

        assert await env.changes(updated) == [
            ("bant", "BANT Label: Budget", "선택 안 함", "풀 예산 확보"),
            ("bant", "BANT Label: Timeline", "선택 안 함", "금년 구매"),
        ]

    async def test_clearing_a_bant_label_is_logged_as_not_selected(self, env: DealEnv) -> None:
        budget = await label_by_name(env.uow, BantCategory.BUDGET, "풀 예산 확보")
        view = await env.new_deal(bant={BantCategory.BUDGET: budget.id})

        updated = await env.update.execute(view.item.deal.id.value, make_patch(bant=_bant()), SALES)

        assert updated.item.deal.bant.get(BantCategory.BUDGET) is None
        assert await env.changes(updated) == [
            ("bant", "BANT Label: Budget", "풀 예산 확보", "선택 안 함")
        ]

    async def test_a_label_of_another_category_is_rejected_and_nothing_changes(
        self, env: DealEnv
    ) -> None:
        need = await label_by_name(env.uow, BantCategory.NEED, "모름")
        view = await env.new_deal()

        with raises_with(InvalidBantLabelError, "BANT Label이 올바르지 않습니다."):
            await env.update.execute(
                view.item.deal.id.value, make_patch(bant=_bant(budget=need.id)), SALES
            )

        assert await env.changes(view) == []


class TestAtomicity:
    @pytest.mark.parametrize(
        ("patch", "message"),
        [
            ({"name": "  "}, "Deal Name을 입력하세요."),
            ({"revenue_amount": 0}, "매출금액은 1원 이상의 정수로 입력하세요."),
            ({"revenue_date": None}, "Expected Close를 입력하세요."),
            ({"users": 0}, "Users는 1 이상의 정수로 입력하세요."),
            ({"procurement": "가" * 501}, "구매절차는 500자 이내로 입력하세요."),
        ],
    )
    async def test_a_sent_invalid_field_is_rejected_and_nothing_changes(
        self, env: DealEnv, patch: dict[str, object], message: str
    ) -> None:
        view = await env.new_deal()
        contacts_before = len(env.uow.contacts._items)

        with raises_with(InvalidValueError, message):
            await env.update.execute(
                view.item.deal.id.value,
                make_patch(customer=make_draft(company="새고객"), **patch),
                SALES,
            )

        stored = await env.uow.deals.get(view.item.deal.id)
        assert stored.details == view.item.deal.details
        assert len(env.uow.contacts._items) == contacts_before  # 새 고객 연락처도 없다
        assert await env.changes(view) == []

    async def test_the_first_invalid_field_in_the_agreed_order_is_reported(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

        with raises_with(InvalidValueError, "Deal Name을 입력하세요."):
            await env.update.execute(
                view.item.deal.id.value,
                make_patch(name="", revenue_amount=0, users=0, status_key="zzz"),
                SALES,
            )
