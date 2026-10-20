"""DealRepository 계약(AC-15·17·19): Next Action 기준 행과 상태 필터. Fake와 SQL에 같은 기대값.

기준 행 = Next Action이 있는 가장 최근 Action(진행사항만 있는 행은 건너뜀). 최종 업데이트는
모든 Action(진행사항만 있는 행 포함)과 Deal 수정 시각 중 늦은 쪽이다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.domain.deal_action.next_action_status import NextActionStatus

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery, NextActionSummary
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def _codes(case: DealCase, **query: object) -> list[str]:
    found = await case.deals.search(DealQuery(**query))  # type: ignore[arg-type]
    return sorted(i.deal.id.value for i in found)


async def test_deal_list_next_action_skips_progress_only_rows(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(
        deal, acted_at=later(100), next_action="계약서 검토", due_date=date(2026, 2, 5)
    )
    await deal_case.add_action(deal, acted_at=later(200), action="통화만", next_action="")

    (listed,) = await deal_case.deals.search(DealQuery())
    detail = await deal_case.deals.get_item(deal.id)

    expected = NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert listed.next_action == expected
    assert detail.next_action == expected


async def test_deal_with_only_progress_only_actions_has_no_next_action(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")

    item = await deal_case.deals.get_item(deal.id)

    assert item.next_action is None


async def test_last_updated_counts_progress_only_rows(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="계약서 검토")
    await deal_case.add_action(deal, acted_at=later(300), action="통화만", next_action="")

    (listed,) = await deal_case.deals.search(DealQuery())
    detail = await deal_case.deals.get_item(deal.id)

    assert listed.last_updated_at == later(300)
    assert detail.last_updated_at == later(300)


async def test_last_updated_of_a_progress_only_deal_uses_that_action(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")

    assert (await deal_case.deals.get_item(deal.id)).last_updated_at == later(100)


async def test_last_updated_falls_back_to_deal_created_at_without_actions(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.touch([deal.id], later(50))  # Deal 수정은 반영하지 않는다

    assert (await deal_case.deals.get_item(deal.id)).last_updated_at == later(5)


async def test_basis_row_status_is_listed(deal_case: DealCase) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    action = await deal_case.add_action(deal, acted_at=later(100), next_action="견적")
    await deal_case.set_next_action_status(action, "not_done", later(150))

    item = await deal_case.deals.get_item(deal.id)

    assert item.next_action is not None
    assert item.next_action.status is NextActionStatus.NOT_DONE


async def _seed_three(case: DealCase) -> tuple[Deal, Deal, Deal]:
    """A: 기준 행 done 뒤에 진행사항만, B: 기준 행 open, C: 진행사항만."""
    a = make_deal(later(5), code="20261016-A001")
    b = make_deal(later(5), code="20261016-A002")
    c = make_deal(later(5), code="20261016-A003")
    for deal in (a, b, c):
        await case.add(deal)
    done = await case.add_action(a, acted_at=later(100), next_action="A 계획")
    await case.set_next_action_status(done, "done", later(120))
    await case.add_action(a, acted_at=later(200), action="A 진행", next_action="")
    await case.add_action(b, acted_at=later(100), next_action="B 계획")
    await case.add_action(c, acted_at=later(100), action="C 진행", next_action="")
    return a, b, c


async def test_deal_list_filters_by_latest_next_action_status(deal_case: DealCase) -> None:
    await _seed_three(deal_case)

    assert await _codes(deal_case, next_action_status=NextActionStatusFilter.OPEN) == [
        "20261016-A002"
    ]
    assert await _codes(deal_case, next_action_status=NextActionStatusFilter.DONE) == [
        "20261016-A001"
    ]
    assert await _codes(deal_case, next_action_status=NextActionStatusFilter.NOT_DONE) == []


async def test_deal_list_closed_filter_matches_done_and_not_done(deal_case: DealCase) -> None:
    a, b, _ = await _seed_three(deal_case)
    older = await deal_case.add_action(b, acted_at=later(50), next_action="B 예전 계획")
    await deal_case.set_next_action_status(older, "done", later(60))  # 기준 행이 아니다

    assert await _codes(deal_case, next_action_status=NextActionStatusFilter.CLOSED) == [a.id.value]


async def test_deal_list_closed_filter_includes_not_done_basis(deal_case: DealCase) -> None:
    _, b, _ = await _seed_three(deal_case)
    (action,) = await deal_case.actions_of(b.id)
    await deal_case.set_next_action_status(action, "not_done", later(150))

    assert await _codes(deal_case, next_action_status=NextActionStatusFilter.CLOSED) == [
        "20261016-A001",
        "20261016-A002",
    ]


async def test_deal_list_status_filter_excludes_deals_without_next_action(
    deal_case: DealCase,
) -> None:
    await _seed_three(deal_case)
    await deal_case.add(make_deal(later(5), code="20261016-A004"))  # Action 자체가 없는 Deal

    for status in NextActionStatusFilter:
        assert "20261016-A003" not in await _codes(deal_case, next_action_status=status)
        assert "20261016-A004" not in await _codes(deal_case, next_action_status=status)


async def test_deal_list_without_status_filter_returns_every_deal(deal_case: DealCase) -> None:
    await _seed_three(deal_case)

    assert await _codes(deal_case) == ["20261016-A001", "20261016-A002", "20261016-A003"]


async def test_deal_count_uses_the_same_status_condition(deal_case: DealCase) -> None:
    await _seed_three(deal_case)
    query = DealQuery(next_action_status=NextActionStatusFilter.CLOSED)

    assert await deal_case.deals.count(query) == len(await deal_case.deals.search(query)) == 1
    assert await deal_case.deals.count(DealQuery()) == 3


async def test_deal_edit_does_not_change_the_last_update_of_a_deal_with_actions(
    deal_case: DealCase,
) -> None:
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")
    await deal_case.deals.touch([deal.id], later(900))

    assert (await deal_case.deals.get_item(deal.id)).last_updated_at == later(100)


async def test_default_order_follows_action_time_not_deal_edits(deal_case: DealCase) -> None:
    edited = make_deal(later(5), code="20261016-A001")
    acted = make_deal(later(5), code="20261016-A002")
    await deal_case.add(edited)
    await deal_case.add(acted)
    await deal_case.add_action(acted, acted_at=later(100))
    await deal_case.deals.touch([edited.id], later(900))

    found = await deal_case.deals.search(DealQuery())

    assert [i.deal.id.value for i in found] == ["20261016-A002", "20261016-A001"]
