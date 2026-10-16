"""ListDeals(AC-22·22a·22e, R2): 기본 정렬, total, 페이지, keyword·owner·vendor·status·기간.

solution·forecast·연/분기·BANT 필터와 정렬 선택은 R3다. 여기서는 기본 정렬(last_updated_at
내림차순, 동률은 code 오름차순)만 본다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.auth.principal import Role
from tests.factories import NOW, later
from tests.factories_deal import (
    SALES,
    draft_of,
    make_draft,
    make_patch,
    new_customer,
    seed_deal,
)
from tests.support.auth_seed import seed_user

if TYPE_CHECKING:
    from app.application.deal.dto import DealPage

    from tests.unit.application.deal_env import DealEnv


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


async def test_the_page_carries_items_total_offset_and_limit(env: DealEnv) -> None:
    for _ in range(3):
        await env.new_deal()

    page = await env.list.execute(DealQuery(offset=1, limit=1))

    assert (len(page.items), page.total, page.offset, page.limit) == (1, 3, 1, 1)


async def test_the_default_order_is_the_most_recently_updated_first(env: DealEnv) -> None:
    first = await env.new_deal()
    second = await env.new_deal()
    third = await env.new_deal()

    page = await env.list.execute(DealQuery())

    assert _codes(page) == [v.item.deal.id.value for v in (third, second, first)]


async def test_equal_update_times_are_ordered_by_code_ascending(env: DealEnv) -> None:
    for code in ("20261016-C003", "20261016-A001", "20261016-B002"):
        await seed_deal(env.uow, code=code, now=NOW)

    page = await env.list.execute(DealQuery())

    assert _codes(page) == ["20261016-A001", "20261016-B002", "20261016-C003"]


async def test_editing_a_deal_moves_it_to_the_top(env: DealEnv) -> None:
    old = await env.new_deal()
    newer = await env.new_deal()
    env.clock.advance(60)
    await env.update.execute(old.item.deal.id.value, make_patch(name="수정됨"), SALES)

    page = await env.list.execute(DealQuery())

    assert _codes(page) == [old.item.deal.id.value, newer.item.deal.id.value]


async def test_total_is_the_filtered_count_regardless_of_the_page(env: DealEnv) -> None:
    for number in range(5):
        await env.new_deal(vendor="SAP" if number < 3 else "Oracle")

    page = await env.list.execute(DealQuery(vendor="SAP", offset=2, limit=1))

    assert (len(page.items), page.total) == (1, 3)


async def test_an_empty_result_has_no_items_and_zero_total(env: DealEnv) -> None:
    await env.new_deal()

    page = await env.list.execute(DealQuery(vendor="없는 Vendor"))

    assert (page.items, page.total) == ([], 0)


async def test_each_row_has_the_owner_customer_and_active_partner(env: DealEnv) -> None:
    await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )

    (view,) = (await env.list.execute(DealQuery())).items

    assert view.owner.role is Role.SALES
    assert view.customer.details.company == "한빛은행"
    active = view.item.deal.active_partner_id()
    assert active is not None
    assert view.partner_contacts[active].details.company == "코어테크"
    assert view.item.next_action is None
    assert view.item.last_updated_at == view.item.deal.updated_at


class TestKeyword:
    async def test_matches_the_deal_name_ignoring_case(self, env: DealEnv) -> None:
        hit = await env.new_deal(name="ERP 구축")
        await env.new_deal(name="CRM")

        page = await env.list.execute(DealQuery(keyword="erp"))

        assert _codes(page) == [hit.item.deal.id.value]

    async def test_matches_the_customer_company(self, env: DealEnv) -> None:
        hit = await env.new_deal(customer=make_draft(company="한빛은행", name="정민수"))
        await env.new_deal(customer=make_draft(company="대한상사", name="오세훈"))

        page = await env.list.execute(DealQuery(keyword="한빛"))

        assert _codes(page) == [hit.item.deal.id.value]

    async def test_matches_the_active_partner_company_only(self, env: DealEnv) -> None:
        active = await env.new_deal(partner=make_draft(company="코어테크", name="민지훈"))
        replaced = await env.new_deal(partner=make_draft(company="에이원시스템", name="표성호"))
        await env.update.execute(
            replaced.item.deal.id.value,
            make_patch(partner=make_draft(company="대한파트너", name="최민수")),
            SALES,
        )

        assert _codes(await env.list.execute(DealQuery(keyword="코어테크"))) == [
            active.item.deal.id.value
        ]
        assert _codes(await env.list.execute(DealQuery(keyword="에이원"))) == []  # 비활성 링크
        assert _codes(await env.list.execute(DealQuery(keyword="대한파트너"))) == [
            replaced.item.deal.id.value
        ]

    async def test_matches_a_part_of_the_deal_code(self, env: DealEnv) -> None:
        hit = await env.new_deal()
        await env.new_deal()

        suffix = hit.item.deal.id.value.split("-")[1]
        page = await env.list.execute(DealQuery(keyword=suffix.lower()))

        assert hit.item.deal.id.value in _codes(page)

    async def test_percent_and_underscore_are_literal_characters(self, env: DealEnv) -> None:
        hit = await env.new_deal(name="100% 달성_목표")
        await env.new_deal(name="1000 달성X목표")

        assert _codes(await env.list.execute(DealQuery(keyword="100%"))) == [hit.item.deal.id.value]
        assert _codes(await env.list.execute(DealQuery(keyword="_목표"))) == [
            hit.item.deal.id.value
        ]


class TestFilters:
    async def test_owner_matches_exactly(self, env: DealEnv) -> None:
        park = await seed_user(env.uow_factory, "park", Role.SALES)
        mine = await env.new_deal()
        theirs = await env.new_deal(owner_user_id=park.id)

        assert _codes(await env.list.execute(DealQuery(owner_user_id=park.id))) == [
            theirs.item.deal.id.value
        ]
        assert mine.item.deal.id.value in _codes(await env.list.execute(DealQuery()))

    async def test_vendor_matches_exactly_and_case_sensitively(self, env: DealEnv) -> None:
        hit = await env.new_deal(vendor="SAP")
        await env.new_deal(vendor="SAP Korea")
        await env.new_deal(vendor="sap")

        assert _codes(await env.list.execute(DealQuery(vendor="SAP"))) == [hit.item.deal.id.value]

    async def test_status_matches_the_status_key(self, env: DealEnv) -> None:
        await env.new_deal(status_key="prospecting")
        hit = await env.new_deal(status_key="price_negotiation")

        page = await env.list.execute(DealQuery(status_key="price_negotiation"))

        assert _codes(page) == [hit.item.deal.id.value]

    async def test_an_unknown_status_key_is_zero_results_not_an_error(self, env: DealEnv) -> None:
        await env.new_deal()

        page = await env.list.execute(DealQuery(status_key="no_such_status"))

        assert (page.items, page.total) == ([], 0)

    async def test_the_revenue_period_includes_both_ends(self, env: DealEnv) -> None:
        days = {
            "before": date(2026, 5, 31),
            "from": date(2026, 6, 1),
            "inside": date(2026, 6, 15),
            "to": date(2026, 6, 30),
            "after": date(2026, 7, 1),
        }
        views = {name: await env.new_deal(revenue_date=day) for name, day in days.items()}

        page = await env.list.execute(
            DealQuery(revenue_from=date(2026, 6, 1), revenue_to=date(2026, 6, 30))
        )

        assert set(_codes(page)) == {views[n].item.deal.id.value for n in ("from", "inside", "to")}

    async def test_a_single_day_period_is_allowed(self, env: DealEnv) -> None:
        hit = await env.new_deal(revenue_date=date(2026, 6, 1))
        await env.new_deal(revenue_date=date(2026, 6, 2))

        page = await env.list.execute(
            DealQuery(revenue_from=date(2026, 6, 1), revenue_to=date(2026, 6, 1))
        )

        assert _codes(page) == [hit.item.deal.id.value]

    async def test_conditions_are_combined_with_and(self, env: DealEnv) -> None:
        hit = await env.new_deal(name="ERP", vendor="SAP", status_key="introduction")
        await env.new_deal(name="ERP", vendor="Oracle", status_key="introduction")
        await env.new_deal(name="ERP", vendor="SAP", status_key="prospecting")
        await env.new_deal(name="CRM", vendor="SAP", status_key="introduction")

        page = await env.list.execute(
            DealQuery(keyword="erp", vendor="SAP", status_key="introduction")
        )

        assert _codes(page) == [hit.item.deal.id.value]

    async def test_a_reused_customer_contact_is_found_by_its_company(self, env: DealEnv) -> None:
        customer = new_customer()
        deal = await seed_deal(env.uow, customer=customer, now=later(1))
        await env.new_deal(customer=draft_of(customer))

        page = await env.list.execute(DealQuery(keyword=customer.details.company))

        assert deal.id.value in _codes(page)
        assert page.total == 2
