"""ListDeals: BDD 케이스(DL)가 덮지 않는 세부 동작(페이지 필드, 동률 순서, 행 구성, 재사용 연락처).

조건 검색·기간·정렬 케이스는 `test_deal_list_search_cases.py`·
`test_deal_list_period_sort_cases.py`가 정본이다. 여기에는 그 케이스에 없는 단언만 남겼다.
"""

from typing import TYPE_CHECKING

from app.application.deal.dto import NamedRef
from app.application.ports.deal_repository import DealQuery
from app.domain.auth.principal import Role
from app.domain.vendor.values import VendorId
from tests.factories import NOW, later
from tests.factories_deal import (
    SALES,
    draft_of,
    make_draft,
    make_patch,
    new_customer,
    seed_deal,
)
from tests.support.ids import new_id

if TYPE_CHECKING:
    from app.application.deal.dto import DealPage
    from tests.unit.application.deal_env import DealEnv


def _codes(page: DealPage) -> list[str]:
    return [view.item.deal.id.value for view in page.items]


async def test_the_page_carries_items_total_offset_and_limit(env: DealEnv) -> None:
    """페이지 응답은 요청한 offset·limit과 전체 total, 그 구간의 항목 수를 담는다."""
    # given: Deal 세 개
    for _ in range(3):
        await env.new_deal()

    # when: offset 1, limit 1로 조회한다
    page = await env.list.execute(DealQuery(offset=1, limit=1))

    # then: 항목 1개, total 3, offset·limit은 요청 그대로다
    assert (len(page.items), page.total, page.offset, page.limit) == (1, 3, 1, 1)


async def test_equal_update_times_are_ordered_by_code_ascending(env: DealEnv) -> None:
    """기본 정렬에서 최종 업데이트 시각이 같으면 code 오름차순이다."""
    # given: 같은 시각에 갱신된 Deal 셋(code 순서가 등록 순서와 다름)
    for code in ("20261016-C003", "20261016-A001", "20261016-B002"):
        await seed_deal(env.uow, code=code, now=NOW)

    # when: 기본 정렬로 조회한다
    page = await env.list.execute(DealQuery())

    # then: code 오름차순이다
    assert _codes(page) == ["20261016-A001", "20261016-B002", "20261016-C003"]


async def test_editing_a_deal_does_not_move_it_in_the_list(env: DealEnv) -> None:
    """Deal을 수정해도 기본 정렬 순서는 바뀌지 않는다(최종 업데이트는 Action 기준)."""
    # given: 두 Deal의 기본 정렬 순서와, 오래된 쪽 Deal의 수정
    old = await env.new_deal()
    newer = await env.new_deal()
    before = _codes(await env.list.execute(DealQuery()))
    env.clock.advance(60)
    await env.update.execute(old.item.deal.id.value, make_patch(name="수정됨"), SALES)

    # when: 기본 정렬로 다시 조회한다
    page = await env.list.execute(DealQuery())

    # then: 순서가 수정 전과 같다
    assert _codes(page) == before
    assert set(before) == {old.item.deal.id.value, newer.item.deal.id.value}


async def test_each_row_has_the_owner_customer_and_active_partner(env: DealEnv) -> None:
    """목록 행은 담당자·고객·활성 파트너 연락처와 파생 값을 담는다."""
    # given: 고객과 파트너가 있는 Deal
    await env.new_deal(
        customer=make_draft(company="한빛은행", name="정민수"),
        partner=make_draft(company="코어테크", name="민지훈"),
    )

    # when: 조회한다
    (view,) = (await env.list.execute(DealQuery())).items

    # then: 담당자 역할·고객 회사·활성 파트너 회사가 있고 Action이 없어 next_action은 없다
    assert view.owner.role is Role.SALES
    assert view.customer.details.company == "한빛은행"
    active = view.item.deal.active_partner_id()
    assert active is not None
    assert view.partner_contacts[active].details.company == "코어테크"
    assert view.item.next_action is None
    assert view.item.last_updated_on == view.item.deal.created_at.astimezone().date()


class TestFilters:
    async def test_list_views_have_vendor_ref_and_solution_text(self, env: DealEnv) -> None:
        """목록 행은 Vendor 참조(id·이름)와 Solution 텍스트를 담는다."""
        # given: SAP Deal 둘과 Oracle Deal(Solution은 선택이라 빈 값도 있다)
        sap = await env.new_vendor("SAP")
        oracle = await env.new_vendor("Oracle")
        await env.new_deal(vendor_id=sap.id, solution="S/4HANA")
        await env.new_deal(vendor_id=sap.id, solution="BW")
        await env.new_deal(vendor_id=oracle.id, solution="MFA")

        # when: 조회한다
        views = (await env.list.execute(DealQuery())).items

        # then: 행마다 (Vendor 참조, Solution 텍스트)가 맞고 별도 solution 속성은 없다
        shown = {(v.vendor, v.item.deal.details.solution) for v in views}
        assert shown == {
            (NamedRef(sap.id, "SAP"), "S/4HANA"),
            (NamedRef(sap.id, "SAP"), "BW"),
            (NamedRef(oracle.id, "Oracle"), "MFA"),
        }
        assert all(not hasattr(v, "solution") for v in views)

    async def test_unknown_vendor_id_returns_nothing(self, env: DealEnv) -> None:
        """없는 Vendor id와 맞는 것이 없는 Solution 텍스트는 오류 없이 0건이다."""
        # given: Deal 하나
        await env.new_deal()

        # when: 없는 Vendor id로, 맞는 것 없는 Solution으로 각각 조회한다
        page = await env.list.execute(DealQuery(vendor_id=VendorId(new_id())))
        by_solution = await env.list.execute(DealQuery(solution="no-such"))

        # then: 둘 다 빈 목록과 total 0이다
        assert (page.items, page.total, by_solution.total) == ([], 0, 0)

    async def test_a_reused_customer_contact_is_found_by_its_company(self, env: DealEnv) -> None:
        """같은 고객 연락처를 재사용한 Deal들은 그 회사명 키워드로 모두 찾는다."""
        # given: 같은 고객 연락처를 쓰는 Deal 둘
        customer = new_customer()
        deal = await seed_deal(env.uow, customer=customer, now=later(1))
        await env.new_deal(customer=draft_of(customer))

        # when: 그 회사명으로 검색한다
        page = await env.list.execute(DealQuery(keyword=customer.details.company))

        # then: 두 Deal이 모두 나온다
        assert deal.id.value in _codes(page)
        assert page.total == 2
