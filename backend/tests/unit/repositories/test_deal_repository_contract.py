"""DealRepository 저장·조회 계약: Fake와 SQL(PostgreSQL)에 같은 기대값을 적용한다.

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
from app.domain.deal.values import (
    AMOUNT_MAX,
    USERS_MAX,
    Poc,
    PocState,
    Quote,
    QuoteSubmitted,
    RevenueAmount,
)
from tests.factories import NOW, make_bant, make_deal, make_deal_code, new_contact_id
from tests.support.legacy_solution import blank_solution
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
        """Deal의 모든 필드가 저장 후 그대로 읽힌다."""
        # given: 모든 필드를 채운 Deal
        partner = await deal_case.new_contact(ContactKind.PARTNER)
        customer = await deal_case.new_contact()
        budget = await deal_case.new_label(BantCategory.BUDGET, "테스트 예산")
        sap = await deal_case.new_vendor("ZZ SAP")
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
            solution="S/4HANA",
            users=250,
            revenue_amount=1_870_000_000,
            revenue_date=date(2026, 12, 31),
            quote=Quote(QuoteSubmitted.YES, date(2026, 10, 1)),
            poc=Poc(PocState.ING, date(2026, 11, 1)),
            procurement="조달청 입찰",
        )
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (모든 필드)
        loaded = await deal_case.deals.get(deal.id)

        # then: 값은 같고 별도 객체이며 모든 필드가 보존된다
        assert loaded == deal
        assert loaded is not deal
        assert loaded.details == deal.details
        assert loaded.sync == deal.sync
        assert loaded.customer_id == customer.id
        assert loaded.partner_links == deal.partner_links
        assert loaded.bant == deal.bant
        assert (loaded.created_at, loaded.updated_at) == (NOW, NOW)

    async def test_legacy_empty_solution_round_trips(self, deal_case: DealCase) -> None:
        """빈 Solution을 가진 예전 Deal도 저장하고 그대로 읽는다."""
        # Solution 도입 전 행(빈 문자열)도 저장하고 그대로 읽는다(리뷰 후속 결정).
        # given: Solution이 빈 예전 Deal
        deal = make_deal(NOW, code=CODE, customer_id=(await _referenceable_customer(deal_case)).id)
        blank_solution(deal)
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (빈 Solution)
        loaded = await deal_case.deals.get(deal.id)

        # then: Solution이 빈 문자열 그대로다
        assert loaded.details.solution == ""
        assert loaded.details == deal.details

    async def test_legacy_empty_solution_survives_update(self, deal_case: DealCase) -> None:
        """빈 Solution은 다른 필드를 수정해도 유지된다."""
        # given: Solution이 빈 Deal을 저장하고 읽어 온 상태
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(NOW, code=CODE, customer_id=customer.id)
        blank_solution(deal)
        await deal_case.add(deal)
        loaded = await deal_case.deals.get(deal.id)

        # when: 금액만 바꿔 수정한다 (전제: Fake·SQL 공통)
        loaded.change_revenue_amount(RevenueAmount(4_000))
        await deal_case.deals.update(loaded)

        # then: 금액은 바뀌고 Solution은 빈 문자열이다
        reloaded = await deal_case.deals.get(deal.id)
        assert (reloaded.details.revenue_amount.value, reloaded.details.solution) == (4_000, "")

    async def test_extreme_values_round_trip(self, deal_case: DealCase) -> None:
        """금액·사용자 수의 최댓값이 저장 후 그대로 읽힌다."""
        # given: 금액과 사용자 수가 최댓값인 Deal
        deal = make_deal(code=CODE, revenue_amount=AMOUNT_MAX, users=USERS_MAX)
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (최댓값)
        loaded = await deal_case.deals.get(deal.id)

        # then: 최댓값이 그대로다
        assert loaded.details.revenue_amount.value == AMOUNT_MAX
        assert (loaded.details.users, loaded.details.vendor_id, loaded.details.solution) == (
            USERS_MAX,
            None,
            "S/4HANA",
        )

    async def test_solution_text_round_trips(self, deal_case: DealCase) -> None:
        """한글이 섞인 Solution 텍스트가 그대로 읽힌다."""
        # given: 한글·기호가 섞인 Solution의 Deal
        deal = make_deal(code=CODE, solution="ITDR 2.0 / 한글 Solution")
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (한글 Solution)
        loaded = await deal_case.deals.get(deal.id)

        # then: Solution이 그대로다
        assert loaded.details.solution == "ITDR 2.0 / 한글 Solution"

    async def test_solution_text_is_saved_without_a_vendor(self, deal_case: DealCase) -> None:
        """Vendor 없이도 Solution 텍스트를 저장한다."""
        # given: Vendor 없이 Solution만 있는 Deal
        deal = make_deal(code=CODE, vendor_id=None, solution="ITDR")
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (Vendor 없는 Solution)
        loaded = await deal_case.deals.get(deal.id)
        # then: Vendor는 None이고 Solution이 남아 있다
        assert (loaded.details.vendor_id, loaded.details.solution) == (None, "ITDR")

    async def test_solution_text_of_200_characters_round_trips(self, deal_case: DealCase) -> None:
        """200자 Solution이 그대로 읽힌다."""
        # given: Solution이 200자인 Deal
        deal = make_deal(code=CODE, solution="가" * 200)
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (200자 Solution)
        loaded = await deal_case.deals.get(deal.id)

        # then: 200자가 그대로다
        assert loaded.details.solution == "가" * 200

    async def test_the_owner_is_a_user_id(self, deal_case: DealCase) -> None:
        """담당자는 사용자 id로 저장된다."""
        # given: 사용자 id가 담당자인 Deal
        deal = make_deal(code=CODE, owner_user_id=uid("alice"))
        await deal_case.add(deal)

        # when: 저장한 Deal을 조회한다 (전제: Fake·SQL 공통) (담당자 id)
        loaded = await deal_case.deals.get(deal.id)

        # then: 담당자 id가 그대로다
        assert loaded.details.owner_user_id == uid("alice")

    async def test_a_missing_deal_is_not_found(self, deal_case: DealCase) -> None:
        """없는 Deal을 조회하면 없음 오류다."""
        # when·then: 없는 코드로 조회하면 DealNotFoundError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(DealNotFoundError):
            await deal_case.deals.get(make_deal_code("ZZZZ"))

    async def test_exists_tells_whether_the_code_is_stored(self, deal_case: DealCase) -> None:
        """exists는 코드가 저장돼 있는지 알려 준다."""
        # given: 저장된 Deal
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        # when: 저장된 코드와 없는 코드로 존재 여부를 묻는다 (전제: Fake·SQL 공통)
        stored = await deal_case.deals.exists(deal.id)
        missing = await deal_case.deals.exists(make_deal_code("ZZZZ"))

        # then: 저장된 코드는 True, 없는 코드는 False다
        assert stored is True
        assert missing is False

    async def test_get_for_update_returns_the_same_deal(self, deal_case: DealCase) -> None:
        """행 잠금으로 조회해도 같은 Deal을 얻는다."""
        # given: 저장된 Deal
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        # when: for_update로 조회한다 (전제: Fake·SQL 공통)
        locked = await deal_case.deals.get(deal.id, for_update=True)

        # then: 같은 Deal이다
        assert locked == deal

    async def test_get_item_has_no_derived_values_when_there_are_no_actions(
        self, deal_case: DealCase
    ) -> None:
        """Action이 없으면 목록 항목에 파생값이 없다."""
        # given: Action 없는 Deal
        deal = make_deal(code=CODE)
        await deal_case.add(deal)

        # when: 목록 항목을 조회한다 (전제: Fake·SQL 공통)
        item = await deal_case.deals.get_item(deal.id)

        # then: Next Action은 없고 최종 업데이트는 Deal 수정 시각이다
        assert item.deal == deal
        assert item.next_action is None
        assert item.last_updated_at == deal.updated_at

    async def test_get_item_of_a_missing_deal_is_not_found(self, deal_case: DealCase) -> None:
        """없는 Deal의 목록 항목을 조회하면 없음 오류다."""
        # when·then: 없는 코드로 조회하면 DealNotFoundError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(DealNotFoundError):
            await deal_case.deals.get_item(make_deal_code("ZZZZ"))


class TestDuplicateCode:
    async def test_the_same_code_raises_duplicate(self, deal_case: DealCase) -> None:
        """같은 코드를 다시 저장하면 중복 오류다."""
        # given: 저장된 Deal
        await deal_case.add(make_deal(code=CODE))

        # when·then: 같은 코드의 Deal을 추가하면 DuplicateDealCodeError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(DuplicateDealCodeError):
            await deal_case.add(make_deal(code=CODE, name="다른 딜"))

    async def test_the_transaction_stays_usable_after_a_duplicate_code(
        self, deal_case: DealCase
    ) -> None:
        """중복 오류 뒤에도 같은 트랜잭션을 계속 쓸 수 있다."""
        # given: 저장된 Deal과 한 번 겪은 중복 오류
        await deal_case.add(make_deal(code=CODE))
        with pytest.raises(DuplicateDealCodeError):
            await deal_case.add(make_deal(code=CODE, name="다른 딜"))

        # when: 다른 코드의 Deal을 추가한다 (전제: Fake·SQL 공통)
        other = make_deal(code="20261016-A002")
        await deal_case.add(other)

        # then: 새 Deal과 기존 Deal을 모두 조회할 수 있다
        added = await deal_case.deals.get(other.id)
        first = await deal_case.deals.get(make_deal_code("A001"))

        assert added.id == other.id
        assert first.details.name == "ERP 구축"

    async def test_a_duplicate_leaves_no_partial_rows(self, deal_case: DealCase) -> None:
        """중복 오류가 일부 행을 남기지 않는다."""
        # given: 저장된 Deal과 파트너 연락처
        await deal_case.add(make_deal(code=CODE))
        partner = await deal_case.new_contact(ContactKind.PARTNER)

        # when·then: 같은 코드를 추가하면 DuplicateDealCodeError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(DuplicateDealCodeError):
            await deal_case.deals.add(make_deal(code=CODE, partner_id=partner.id))

        # then: 기존 Deal에 파트너 링크가 생기지 않았다
        stored = await deal_case.deals.get(make_deal_code("A001"))

        assert stored.partner_links == []


class TestReferences:
    async def test_a_missing_customer_is_an_invalid_reference(self, deal_case: DealCase) -> None:
        """없는 고객 연락처는 잘못된 참조 오류다."""
        # given: 담당자만 있는 상태
        await deal_case.ensure_owner()

        # when·then: 없는 고객이면 InvalidReferenceError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(make_deal(code=CODE, customer_id=new_contact_id()))

    async def test_a_missing_partner_contact_is_an_invalid_reference(
        self, deal_case: DealCase
    ) -> None:
        """없는 파트너 연락처는 잘못된 참조 오류다."""
        # given: 고객 연락처만 있는 상태
        customer = await _referenceable_customer(deal_case)

        # when·then: 없는 파트너면 InvalidReferenceError가 난다 (전제: Fake·SQL 공통)
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
        """모르는 Status·Forecast 키는 잘못된 참조 오류다."""
        # given: 모르는 키를 가진 Deal
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(
            code=CODE, customer_id=customer.id, status_key=status_key, forecast_key=forecast_key
        )

        # when·then: 추가하면 InvalidReferenceError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)

    async def test_an_unknown_label_is_an_invalid_reference(self, deal_case: DealCase) -> None:
        """모르는 BANT Label은 잘못된 참조 오류다."""
        # given: 없는 Label을 가진 Deal
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(code=CODE, customer_id=customer.id, bant=make_bant(budget=uid("nope")))

        # when·then: 추가하면 InvalidReferenceError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)

    async def test_a_label_of_another_category_is_an_invalid_reference(
        self, deal_case: DealCase
    ) -> None:
        """다른 구분의 BANT Label은 잘못된 참조 오류다."""
        # given: Budget 자리에 Need Label을 쓴 Deal
        need = await deal_case.new_label(BantCategory.NEED, "필요 라벨")
        customer = await _referenceable_customer(deal_case)
        deal = make_deal(code=CODE, customer_id=customer.id, bant=make_bant(budget=need.id))

        # when·then: 추가하면 InvalidReferenceError가 난다 (전제: Fake·SQL 공통)
        with pytest.raises(InvalidReferenceError):
            await deal_case.deals.add(deal)
