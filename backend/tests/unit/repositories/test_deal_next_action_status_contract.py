"""DealRepository 계약: Next Action 기준 행과 상태 필터. Fake와 SQL에 같은 기대값.

기준 행 = Next Action이 있는 가장 최근 Action(진행사항만 있는 행은 건너뜀). 최종 업데이트는
모든 Action(진행사항만 있는 행 포함)과 Deal 수정 시각 중 늦은 쪽이다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery, NextActionSummary
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def _codes(case: DealCase, **query: object) -> list[str]:
    found = await case.deals.search(DealQuery(**query))  # type: ignore[arg-type]
    return sorted(i.deal.id.value for i in found)


async def test_deal_list_next_action_skips_progress_only_rows(deal_case: DealCase) -> None:
    """Deal 목록·상세의 Next Action 요약은 진행사항만 있는 Action을 건너뛴다."""
    # given: Next Action이 있는 Action과, 더 최근의 진행사항만 있는 Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(
        deal, acted_at=later(100), next_action="계약서 검토", due_date=date(2026, 2, 5)
    )
    await deal_case.add_action(deal, acted_at=later(200), action="통화만", next_action="")

    # when: 목록과 상세로 조회한다
    (listed,) = await deal_case.deals.search(DealQuery())
    detail = await deal_case.deals.get_item(deal.id)

    # then: 둘 다 Next Action이 있는 Action의 요약을 보여 준다
    expected = NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert listed.next_action == expected
    assert detail.next_action == expected


async def test_deal_with_only_progress_only_actions_has_no_next_action(
    deal_case: DealCase,
) -> None:
    """진행사항만 있는 Action뿐인 Deal은 Next Action 요약이 없다."""
    # given: 진행사항만 있는 Action 하나를 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")

    # when: 상세로 조회한다
    item = await deal_case.deals.get_item(deal.id)

    # then: Next Action 요약이 없다
    assert item.next_action is None


async def test_last_updated_counts_progress_only_rows(deal_case: DealCase) -> None:
    """최종 업데이트는 진행사항만 있는 Action도 센다."""
    # given: Next Action 있는 Action과, 더 최근의 진행사항만 있는 Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="계약서 검토")
    await deal_case.add_action(deal, acted_at=later(300), action="통화만", next_action="")

    # when: 목록과 상세로 조회한다
    (listed,) = await deal_case.deals.search(DealQuery())
    detail = await deal_case.deals.get_item(deal.id)

    # then: 둘 다 가장 최근 Action의 수행 시각이다
    assert listed.last_updated_at == later(300)
    assert detail.last_updated_at == later(300)


async def test_last_updated_of_a_progress_only_deal_uses_that_action(
    deal_case: DealCase,
) -> None:
    """진행사항만 있는 Deal의 최종 업데이트는 그 Action의 수행 시각이다."""
    # given: 진행사항만 있는 Action 하나를 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")

    # when: 상세로 조회한다
    last_updated = (await deal_case.deals.get_item(deal.id)).last_updated_at
    # then: 최종 업데이트가 그 Action의 수행 시각이다
    assert last_updated == later(100)


async def test_last_updated_falls_back_to_deal_created_at_without_actions(
    deal_case: DealCase,
) -> None:
    """Action이 없으면 최종 업데이트는 Deal 등록 시각이고 Deal 수정은 반영하지 않는다."""
    # given: Action 없이 등록 뒤 수정(touch)된 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.touch([deal.id], later(50))  # Deal 수정은 반영하지 않는다

    # when: 상세로 조회한다
    last_updated = (await deal_case.deals.get_item(deal.id)).last_updated_at
    # then: 최종 업데이트가 Deal 등록 시각이다
    assert last_updated == later(5)


async def test_basis_row_status_is_listed(deal_case: DealCase) -> None:
    """목록 요약에는 기준 Action의 Next Action 상태가 담긴다."""
    # given: Next Action을 미수행으로 종료한 Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    action = await deal_case.add_action(deal, acted_at=later(100), next_action="견적")
    await deal_case.set_next_action_status(action, "not_done", later(150))

    # when: 상세로 조회한다
    item = await deal_case.deals.get_item(deal.id)

    # then: 요약 상태가 미수행이다
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
    """Deal 목록은 기준 Action의 Next Action 상태로 걸러진다."""
    # given: 기준 행이 done인 Deal, open인 Deal, 진행사항만 있는 Deal
    await _seed_three(deal_case)

    # when: Open으로 검색한다
    opened = await _codes(deal_case, next_action_status=NextActionStatusFilter.OPEN)
    # then: 기준 행이 Open인 Deal만 나온다
    assert opened == ["20261016-A002"]
    # when: 수행으로 검색한다
    done = await _codes(deal_case, next_action_status=NextActionStatusFilter.DONE)
    # then: 기준 행이 수행인 Deal만 나온다
    assert done == ["20261016-A001"]
    # when: 미수행으로 검색한다
    not_done = await _codes(deal_case, next_action_status=NextActionStatusFilter.NOT_DONE)
    # then: 결과가 없다
    assert not_done == []


async def test_deal_list_closed_filter_matches_done_and_not_done(deal_case: DealCase) -> None:
    """closed 필터는 기준 행이 종료된 Deal만 찾고 기준이 아닌 옛 행은 보지 않는다."""
    # given: 기준 행이 done인 Deal과, 기준이 아닌 옛 행만 종료된 Open Deal
    a, b, _ = await _seed_three(deal_case)
    older = await deal_case.add_action(b, acted_at=later(50), next_action="B 예전 계획")
    await deal_case.set_next_action_status(older, "done", later(60))  # 기준 행이 아니다

    # when: closed로 검색한다
    found = await _codes(deal_case, next_action_status=NextActionStatusFilter.CLOSED)
    # then: 기준 행이 종료된 Deal만 나온다
    assert found == [a.id.value]


async def test_deal_list_closed_filter_includes_not_done_basis(deal_case: DealCase) -> None:
    """closed 필터는 기준 행이 미수행인 Deal도 찾는다."""
    # given: 기준 행이 done인 Deal과, 기준 행을 미수행으로 종료한 Deal
    _, b, _ = await _seed_three(deal_case)
    (action,) = await deal_case.actions_of(b.id)
    await deal_case.set_next_action_status(action, "not_done", later(150))

    # when: closed로 검색한다
    found = await _codes(deal_case, next_action_status=NextActionStatusFilter.CLOSED)
    # then: 두 Deal이 모두 나온다
    assert found == [
        "20261016-A001",
        "20261016-A002",
    ]


async def test_deal_list_status_filter_excludes_deals_without_next_action(
    deal_case: DealCase,
) -> None:
    """상태 필터는 Next Action이 없는 Deal을 제외한다."""
    # given: 진행사항만 있는 Deal과 Action이 없는 Deal이 섞인 Deal들
    await _seed_three(deal_case)
    await deal_case.add(make_deal(later(5), code="20261016-A004"))  # Action 자체가 없는 Deal

    # when: 모든 상태 필터로 검색한다
    for status in NextActionStatusFilter:
        # then: 진행사항만 있는 Deal은 어느 필터에도 나오지 않는다
        assert "20261016-A003" not in await _codes(deal_case, next_action_status=status)
        # then: Action이 없는 Deal도 어느 필터에도 나오지 않는다
        assert "20261016-A004" not in await _codes(deal_case, next_action_status=status)


async def test_deal_list_without_status_filter_returns_every_deal(deal_case: DealCase) -> None:
    """상태 필터가 없으면 모든 Deal이 나온다."""
    # given: Deal 3건
    await _seed_three(deal_case)

    # when: 필터 없이 검색한다
    found = await _codes(deal_case)
    # then: 3건이 모두 나온다
    assert found == ["20261016-A001", "20261016-A002", "20261016-A003"]


async def test_deal_count_uses_the_same_status_condition(deal_case: DealCase) -> None:
    """Deal 개수 세기는 목록 검색과 같은 상태 조건을 쓴다."""
    # given: Deal 3건 중 closed인 Deal은 1건
    await _seed_three(deal_case)
    query = DealQuery(next_action_status=NextActionStatusFilter.CLOSED)

    # when: closed 조건과 조건 없이 개수를 세고, closed 조건으로 검색한다
    closed_count = await deal_case.deals.count(query)
    found = await deal_case.deals.search(query)
    total = await deal_case.deals.count(DealQuery())
    # then: closed 개수는 검색 결과 수와 같은 1건이고 전체는 3건이다
    assert closed_count == len(found) == 1
    assert total == 3


async def test_deal_edit_does_not_change_the_last_update_of_a_deal_with_actions(
    deal_case: DealCase,
) -> None:
    """Action이 있는 Deal은 Deal 수정으로 최종 업데이트가 바뀌지 않는다."""
    # given: Action이 있는 Deal을 나중에 수정(touch)
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="")
    await deal_case.deals.touch([deal.id], later(900))

    # when: 상세로 조회한다
    last_updated = (await deal_case.deals.get_item(deal.id)).last_updated_at
    # then: 최종 업데이트가 마지막 Action의 수행 시각 그대로다
    assert last_updated == later(100)


async def test_default_order_follows_action_time_not_deal_edits(deal_case: DealCase) -> None:
    """기본 정렬은 Deal 수정이 아니라 Action 수행 시각을 따른다."""
    # given: Action 없이 나중에 수정된 Deal과, Action이 있는 Deal
    edited = make_deal(later(5), code="20261016-A001")
    acted = make_deal(later(5), code="20261016-A002")
    await deal_case.add(edited)
    await deal_case.add(acted)
    await deal_case.add_action(acted, acted_at=later(100))
    await deal_case.deals.touch([edited.id], later(900))

    # when: 기본 정렬로 검색한다
    found = await deal_case.deals.search(DealQuery())

    # then: Action이 있는 Deal이 먼저 나온다
    assert [i.deal.id.value for i in found] == ["20261016-A002", "20261016-A001"]
