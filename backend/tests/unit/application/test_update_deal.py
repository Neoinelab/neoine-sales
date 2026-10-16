"""UpdateDeal(AC-16): 보낸 필드만 반영하고 바뀐 필드마다 이력을 남긴다. 변화가 없으면 흔적 없음."""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal.values import PocState, QuoteSubmitted

from app.domain.auth.principal import Role
from app.domain.deal.errors import DealNotFoundError
from tests.factories_deal import SALES, make_patch
from tests.support.auth_seed import seed_user
from tests.support.expect import raises_with
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

NOT_FOUND = "Deal을 찾을 수 없습니다."


class TestSentFieldsOnly:
    async def test_only_the_sent_fields_change(self, env: DealEnv) -> None:
        view = await env.new_deal(name="ERP 구축", vendor="SAP", solution="S/4HANA")
        env.clock.advance(60)

        updated = await env.update.execute(
            view.item.deal.id.value, make_patch(name="확장 프로젝트"), SALES
        )

        details = updated.item.deal.details
        assert details.name == "확장 프로젝트"
        assert (details.vendor, details.solution) == ("SAP", "S/4HANA")
        assert details.revenue_amount.value == 150_000_000
        assert updated.item.deal.updated_at == env.clock.now()
        assert (await env.uow.deals.get(view.item.deal.id)).details.name == "확장 프로젝트"

    async def test_sending_a_none_value_clears_an_optional_field(self, env: DealEnv) -> None:
        view = await env.new_deal(users=5)

        updated = await env.update.execute(view.item.deal.id.value, make_patch(users=None), SALES)

        assert updated.item.deal.details.users is None
        assert await env.changes(updated) == [("other", "Users", "5", "-")]

    async def test_an_unchanged_value_leaves_no_history_and_keeps_updated_at(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal(name="ERP 구축")
        env.clock.advance(60)

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(name="ERP 구축", revenue_amount=150_000_000, owner_user_id=OWNER_ID),
            SALES,
        )

        assert updated.item.deal.updated_at == view.item.deal.updated_at
        assert await env.changes(updated) == []

    async def test_every_changed_field_is_logged_in_the_fixed_order(self, env: DealEnv) -> None:
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        view = await env.new_deal()

        updated = await env.update.execute(
            view.item.deal.id.value,
            make_patch(
                name="확장 프로젝트",
                vendor="Oracle",
                users=10,
                revenue_amount=200_000_000,
                revenue_date=date(2026, 12, 31),
                owner_user_id=park.id,
                status_key="price_negotiation",
            ),
            SALES,
        )

        assert await env.changes(updated) == [
            ("status", "Status", "기회발굴", "가격협상"),
            ("amount", "금액", "150,000,000원", "200,000,000원"),
            ("expectedClose", "Expected Close", "2026-06-30", "2026-12-31"),
            ("owner", "Owner", "owner", "park"),
            ("other", "Deal Name", "ERP 구축", "확장 프로젝트"),
            ("other", "Vendor", "SAP", "Oracle"),
            ("other", "Users", "-", "10"),
        ]

    async def test_the_history_entries_are_authored_by_the_requester(self, env: DealEnv) -> None:
        view = await env.new_deal()
        env.clock.advance(60)

        await env.update.execute(view.item.deal.id.value, make_patch(name="B"), SALES)

        newest = (await env.uow.deal_history.list(view.item.deal.id))[0]
        assert (newest.changed_by, newest.changed_at) == (SALES.user_id, env.clock.now())

    async def test_quote_poc_and_procurement_are_logged_with_their_formats(
        self, env: DealEnv
    ) -> None:
        view = await env.new_deal()

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

        assert await env.changes(updated) == [
            ("other", "견적", "-", "YES (2026-10-01)"),
            ("other", "POC", "-", "ING"),
            ("other", "구매절차", "-", "조달청 입찰"),
        ]

    async def test_an_unknown_deal_and_a_malformed_code_are_both_not_found(
        self, env: DealEnv
    ) -> None:
        for code in ("20261016-ZZZZ", "bad", "20261016-a7k2", ""):
            with raises_with(DealNotFoundError, NOT_FOUND):
                await env.update.execute(code, make_patch(name="B"), SALES)
