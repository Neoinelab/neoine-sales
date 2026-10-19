"""DealRepository 저장·조회 계약(R2): Fake와 SQL(PostgreSQL)에 같은 기대값을 적용한다.

저장·왕복(링크·BANT 포함), 같은 code 거절 후 계속 쓰기, 참조 위반. 수정·touch는
test_deal_repository_update_contract.py, 삭제는 test_deal_repository_delete_contract.py다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.bant.values import BantCategory
from app.domain.common.errors import InvalidReferenceError
from app.domain.contact.values import ContactKind
from app.domain.deal.errors import DealNotFoundError, DuplicateDealCodeError
from app.domain.deal.values import AMOUNT_MAX, USERS_MAX, Poc, PocState, Quote, QuoteSubmitted
from tests.factories import NOW, make_bant, make_deal, make_deal_code, new_contact_id
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.contact.entities import Contact
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def _referenceable_customer(case: DealCase) -> Contact:
    """저장은 case.deals.add로 직접 할 수 있게 담당자와 고객 연락처 행만 준비한다."""
    await case.ensure_owner()
    return await case.new_contact()


class TestAddAndGet:
    async def test_every_field_round_trips(self, deal_case: DealCase) -> None:
        partner = await deal_case.new_contact(ContactKind.PARTNER)
        customer = await deal_case.new_contact()
        budget = await deal_case.new_label(BantCategory.BUDGET, "테스트 예산")
        sap = await deal_case.new_vendor("ZZ SAP", ("S/4HANA",))
        deal = make_deal(
            NOW,
            code=CODE,
            customer_id=customer.id,
            partner_id=partner.id,
            status_key="price_negotiation",
            forecast_key="commit",
            bant=make_bant(budget=budget.id),
            name="ERP 구축",
            vendor_id=sap.id,
            solution_id=sap.solutions[0].id,
            users=250,
            revenue_amount=1_870_000_000,
            revenue_date=date(2026, 12, 31),
            quote=Quote(QuoteSubmitted.YES, date(2026, 10, 1)),
            poc=Poc(PocState.ING, date(2026, 11, 1)),
            procurement="조달청 입찰",
        )
        await deal_case.add(deal)

        loaded = await deal_case.deals.get(deal.id)

        assert loaded == deal
        assert loaded is not deal
        assert loaded.details == deal.details
        assert loaded.sync == deal.sync
        assert loaded.customer_id == customer.id
        assert loaded.partner_links == deal.partner_links
        assert loaded.bant == deal.bant
        assert (loaded.created_at, loaded.updated_at) == (NOW, NOW)

    async def test_extreme_values_round_trip(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE, revenue_amount=AMOUNT_MAX, users=USERS_MAX)
        await deal_case.add(deal)

        loaded = await deal_case.deals.get(deal.id)

        assert loaded.details.revenue_amount.value == AMOUNT_MAX
        assert (loaded.details.users, loaded.details.vendor_id, loaded.details.solution_id) == (
            USERS_MAX,
            None,
            None,
        )

    async def test_the_owner_is_a_user_id(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE, owner_user_id=uid("alice"))
        await deal_case.add(deal)

        assert (await deal_case.deals.get(deal.id)).details.owner_user_id == uid("alice")

    async def test_a_missing_deal_is_not_found(self, deal_case: DealCase) -> None:
        with pytest.raises(DealNotFoundError):
            await deal_case.deals.get(make_deal_code("ZZZZ"))

    async def test_exists_tells_whether_the_code_is_stored(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        assert await deal_case.deals.exists(deal.id) is True
        assert await deal_case.deals.exists(make_deal_code("ZZZZ")) is False

    async def test_get_for_update_returns_the_same_deal(self, deal_case: DealCase) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        assert await deal_case.deals.get(deal.id, for_update=True) == deal

    async def test_get_item_has_no_derived_values_when_there_are_no_actions(
        self, deal_case: DealCase
    ) -> None:
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        item = await deal_case.deals.get_item(deal.id)

        assert item.deal == deal
        assert item.next_action is None
        assert item.last_updated_at == deal.updated_at

    async def test_get_item_of_a_missing_deal_is_not_found(self, deal_case: DealCase) -> None:
        with pytest.raises(DealNotFoundError):
            await deal_case.deals.get_item(make_deal_code("ZZZZ"))


class TestDuplicateCode:
    async def test_the_same_code_raises_duplicate(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(code=CODE))

        with pytest.raises(DuplicateDealCodeError):
            await deal_case.add(make_deal(code=CODE, name="다른 딜"))

    async def test_the_transaction_stays_usable_after_a_duplicate_code(
        self, deal_case: DealCase
    ) -> None:
        await deal_case.add(make_deal(code=CODE))
        with pytest.raises(DuplicateDealCodeError):
            await deal_case.add(make_deal(code=CODE, name="다른 딜"))

        other = make_deal(code="20261016-A002")
        await deal_case.add(other)

        assert (await deal_case.deals.get(other.id)).id == other.id
        assert (await deal_case.deals.get(make_deal_code("A001"))).details.name == "ERP 구축"

    async def test_a_duplicate_leaves_no_partial_rows(self, deal_case: DealCase) -> None:
        await deal_case.add(make_deal(code=CODE))
        partner = await deal_case.new_contact(ContactKind.PARTNER)

        with pytest.raises(DuplicateDealCodeError):
            await deal_case.deals.add(make_deal(code=CODE, partner_id=partner.id))

        assert (await deal_case.deals.get(make_deal_code("A001"))).partner_links == []


class TestReferences:
    async def test_a_missing_customer_is_an_invalid_reference(self, deal_case: DealCase) -> None:
        await deal_case.ensure_owner()

        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(make_deal(code=CODE, customer_id=new_contact_id()))

    async def test_a_missing_partner_contact_is_an_invalid_reference(
        self, deal_case: DealCase
    ) -> None:
        customer = await _referenceable_customer(deal_case)

        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(
                make_deal(code=CODE, customer_id=customer.id, partner_id=new_contact_id())
            )

    @pytest.mark.parametrize(
        ("status_key", "forecast_key"),
        [("unknown_status", "pipeline"), ("prospecting", "unknown_forecast")],
    )
    async def test_an_unknown_status_or_forecast_key_is_an_invalid_reference(
        self, deal_case: DealCase, status_key: str, forecast_key: str
    ) -> None:
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(
            code=CODE, customer_id=customer.id, status_key=status_key, forecast_key=forecast_key
        )

        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)

    async def test_an_unknown_label_is_an_invalid_reference(self, deal_case: DealCase) -> None:
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(code=CODE, customer_id=customer.id, bant=make_bant(budget=uid("nope")))

        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)

    async def test_a_label_of_another_category_is_an_invalid_reference(
        self, deal_case: DealCase
    ) -> None:
        need = await deal_case.new_label(BantCategory.NEED, "필요 라벨")
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(code=CODE, customer_id=customer.id, bant=make_bant(budget=need.id))

        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)
