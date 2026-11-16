"""UpdateDeal: 보낸 필드만 반영하고 바뀐 필드마다 이력을 남긴다. 변화가 없으면 흔적 없음."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal.inputs import Actor
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.values import PocState, QuoteSubmitted
from tests.factories_deal import SALES, make_draft, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

NOT_FOUND = "Deal을 찾을 수 없습니다."


class TestSentFieldsOnly:
    async def test_only_the_sent_fields_change(self, env: DealEnv) -> None:
        """보낸 필드만 바뀌고 수정 시각은 서버 시각이 된다.

        테스트 코드: DE-036
        """
        # given: Vendor SAP·Product가 있는 Deal.
        sap = await env.new_vendor("SAP")
        view = await env.new_deal(name="ERP 구축", vendor_id=sap.id, product="S/4HANA")
        env.clock.advance(60)

        updated = await env.update.execute(
            view.item.deal.id.value, make_patch(name="확장 프로젝트"), SALES
        )

        # when: 이름만 보내 수정한다.
        details = updated.item.deal.details
        # then: 이름만 바뀌고 Vendor·Product·금액은 그대로이며 updated_at이 서버 시각이다.
        assert details.name == "확장 프로젝트"
        assert (details.vendor_id, details.product) == (sap.id, "S/4HANA")
        assert details.revenue_amount.value == 150_000_000
        assert updated.item.deal.updated_at == env.clock.now()
        assert (await env.uow.deals.get(view.item.deal.id)).details.name == "확장 프로젝트"

    async def test_clearing_users_is_rejected_and_nothing_changes(self, env: DealEnv) -> None:
        """Users count를 null로 고치면 거절되고 값·이력이 그대로다.

        테스트 코드: DE-038
        """
        # given: Users count 5인 Deal.
        view = await env.new_deal(users=5)
        env.uow.commits = 0

        with raises_with(InvalidValueError, "Users count를 입력하세요."):
            await env.update.execute(view.item.deal.id.value, make_patch(users=None), SALES)

        # when: users를 null로 보내 수정한다.
        stored = await env.uow.deals.get(view.item.deal.id)
        # then: 'Users count를 입력하세요.' 오류이고 값 5·커밋·이력이 그대로다.
        assert stored.details.users == 5
        assert env.uow.commits == 0
        assert await env.changes(view) == []

    async def test_users_can_be_set_to_zero(self, env: DealEnv) -> None:
        """Users count는 0으로 고칠 수 있다.

        테스트 코드: DE-038
        """
        # given: Users count 10인 Deal.
        view = await env.new_deal(users=10)

        updated = await env.update.execute(view.item.deal.id.value, make_patch(users=0), SALES)

        # when: users를 0으로 보내 수정한다.
        stored = await env.uow.deals.get(view.item.deal.id)
        # then: 0으로 저장되고 이력이 10 -> 0으로 남는다.
        assert stored.details.users == 0
        assert await env.changes(updated) == [("other", "Users count", "10", "0")]

    async def test_users_not_sent_keeps_the_current_value(self, env: DealEnv) -> None:
        """Users count를 보내지 않는 수정은 값이 그대로다.

        테스트 코드: DE-039
        """
        # given: Users count 5인 Deal.
        view = await env.new_deal(users=5)

        # when: 이름만 보내 수정한다.
        await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        # then: Users count가 5 그대로다.
        assert (await env.uow.deals.get(view.item.deal.id)).details.users == 5

    async def test_an_unchanged_value_leaves_no_history_and_keeps_updated_at(
        self, env: DealEnv
    ) -> None:
        """같은 값만 보내면 이력이 없고 수정 시각도 그대로다.

        테스트 코드: DE-037
        """
        # given: Deal이 있고 시계가 흘렀다.
        view = await env.new_deal(name="ERP 구축")
        env.clock.advance(60)

        # when: 이름·금액·Owner를 현재와 같은 값으로 보낸다.
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(name="ERP 구축", revenue_amount=150_000_000, owner_user_id=OWNER_ID),
            SALES,
        )

        # then: 이력이 없고 updated_at이 그대로다.
        assert updated.item.deal.updated_at == view.item.deal.updated_at
        assert await env.changes(updated) == []

    async def test_every_changed_field_is_logged_in_the_fixed_order(self, env: DealEnv) -> None:
        """바뀐 필드마다 정해진 순서로 이력이 남는다(문구 형식은 DD 소유)."""
        # given: Deal과 다른 sales·Oracle Vendor.
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        oracle = await env.new_vendor("Oracle")
        view = await env.new_deal()  # 기본 Vendor를 고른 Deal

        # when: 여러 필드를 한 번에 고친다.
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                name="확장 프로젝트",
                vendor_id=oracle.id,
                users=20,
                revenue_amount=200_000_000,
                revenue_date=date(2026, 12, 31),
                owner_user_id=park.id,
                status_key="price_negotiation",
            ),
            SALES,
        )

        # then: 바뀐 필드마다 이력이 정해진 순서로 남는다.
        assert await env.changes(updated) == [
            ("status", "Status", "기회발굴", "가격협상"),
            ("amount", "금액(단위:원)", "150,000,000", "200,000,000"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-12-31"),
            ("owner", "Owner", "owner", "park"),
            ("other", "Deal Name", "ERP 구축", "확장 프로젝트"),
            ("other", "Vendor", "기본 Vendor", "Oracle"),
            ("other", "Users count", "10", "20"),
        ]

    async def test_the_history_entries_are_authored_by_the_requester(self, env: DealEnv) -> None:
        """수정 이력의 변경자와 시각은 요청자와 서버 시각이다."""
        # given: Deal이 있다.
        view = await env.new_deal()
        env.clock.advance(60)

        await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        # when: 이름을 고친다.
        newest = (await env.uow.deal_history.list(view.item.deal.id))[0]
        # then: 가장 최근 이력의 변경자·시각이 요청자·서버 시각이다.
        assert (newest.changed_by, newest.changed_at) == (SALES.user_id, env.clock.now())

    async def test_quote_poc_and_procurement_are_logged_with_their_formats(
        self, env: DealEnv
    ) -> None:
        """견적·POC·구매절차 변경이 이력으로 남는다(문구 형식은 DD 소유).

        테스트 코드: DE-036
        """
        # given: Deal이 있다.
        view = await env.new_deal()

        # when: 견적 YES(날짜)·POC ING·구매절차를 보낸다.
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                quote_submitted=QuoteSubmitted.YES,
                quote_submitted_date=date(2026, 10, 1),
                poc_state=PocState.ING,
                poc_completed_date=None,
                procurement="조달청 입찰",
            ),
            SALES,
        )

        # then: 세 항목이 other 이력으로 남는다.
        assert await env.changes(updated) == [
            ("other", "견적", "-", "YES (2026-10-01)"),
            ("other", "POC", "-", "ING"),
            ("other", "구매절차", "-", "조달청 입찰"),
        ]

    async def test_an_unknown_deal_and_a_malformed_code_are_both_not_found(
        self, env: DealEnv
    ) -> None:
        """없는 code와 형식이 틀린 code의 수정은 같은 404다.

        테스트 코드: DE-041
        """
        # when·then: 없는 code, 형식이 틀린 code, 빈 code로 수정한다
        #   → 모두 'Deal을 찾을 수 없습니다.' 오류다.
        for code in ("20261016-ZZZZ", "bad", "20261016-a7k2", ""):
            with raises_with(DealNotFoundError, NOT_FOUND):
                await env.update.execute(code, make_patch(name="B"), SALES)


class TestWhoAndWhatCanBeEdited:
    async def test_a_sales_user_may_edit_a_deal_owned_by_another_sales_user(
        self, env: DealEnv
    ) -> None:
        """sales는 다른 sales가 Owner인 Deal도 수정할 수 있다.

        테스트 코드: DE-043
        """
        # given: KIM이 Owner인 Deal과 다른 sales PARK
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        view = await env.new_deal()
        env.clock.advance(60)

        # when: PARK가 그 Deal의 이름을 고친다
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(name="PARK이 고침"),
            Actor(user_id=park.id, role=Role.SALES),
        )

        # then: 수정되고 Owner는 그대로이며 이력의 변경자는 PARK이다
        assert updated.item.deal.details.name == "PARK이 고침"
        assert updated.item.deal.details.owner_user_id == OWNER_ID
        newest = (await env.uow.deal_history.list(view.item.deal.id))[0]
        assert newest.changed_by == park.id

    @pytest.mark.parametrize(
        ("submitted", "submitted_date", "state", "completed_date"),
        [
            (QuoteSubmitted.NO, date(2026, 10, 1), PocState.ING, date(2026, 11, 1)),
            (None, date(2026, 10, 1), PocState.YES, None),
            (QuoteSubmitted.YES, None, None, date(2026, 11, 1)),
        ],
    )
    async def test_quote_and_poc_are_stored_in_any_combination(
        self,
        env: DealEnv,
        submitted: QuoteSubmitted | None,
        submitted_date: date | None,
        state: PocState | None,
        completed_date: date | None,
    ) -> None:
        """견적·POC는 여부와 날짜의 어떤 조합도 저장한다.

        테스트 코드: DE-062
        """
        # given: 견적·POC가 비어 있는 Deal
        view = await env.new_deal()

        # when: 여부와 날짜가 어긋난 조합을 보낸다
        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                quote_submitted=submitted,
                quote_submitted_date=submitted_date,
                poc_state=state,
                poc_completed_date=completed_date,
            ),
            SALES,
        )

        # then: 조합 검사 없이 보낸 값 그대로 저장된다
        stored = (await env.uow.deals.get(view.item.deal.id)).details
        assert (stored.quote.submitted, stored.quote.submitted_date) == (submitted, submitted_date)
        assert (stored.poc.state, stored.poc.completed_date) == (state, completed_date)
        assert updated.item.deal.details == stored

    async def test_a_null_customer_is_treated_as_an_empty_input(self, env: DealEnv) -> None:
        """customer를 null로 보내면 빈 입력으로 보아 고객 회사명 문구로 거절한다.

        테스트 코드: DE-071
        """
        # given: 고객이 있는 Deal
        view = await env.new_deal()

        # when: customer를 null로 보내 수정한다
        with raises_with(InvalidValueError, "고객 회사명을 입력하세요."):
            await env.update.execute(view.item.deal.id.value, make_patch(customer=None), SALES)

        # then: 회사명 문구의 오류이고 고객·이력이 그대로다
        stored = await env.uow.deals.get(view.item.deal.id)
        assert stored.customer_id == view.customer.id
        assert await env.changes(view) == []

    async def test_a_new_customer_is_not_left_behind_when_a_later_field_fails(
        self, env: DealEnv
    ) -> None:
        """뒤의 필드 검증에 실패하면 새로 입력한 고객 연락처도 남지 않는다.

        테스트 코드: DE-040
        """
        # given: 연락처가 1건 있는 Deal
        view = await env.new_deal()
        contacts_before = len(env.uow.contacts._items)

        # when: 새 고객과 501자 구매절차를 함께 보낸다
        with raises_with(InvalidValueError, "구매절차는 500자 이내로 입력하세요."):
            await env.update.execute(
                view.item.deal.id.value,
                make_patch(customer=make_draft(company="새고객"), procurement="가" * 501),
                SALES,
            )

        # then: 연락처 수와 Deal 이력이 그대로다
        assert len(env.uow.contacts._items) == contacts_before
        assert await env.changes(view) == []
