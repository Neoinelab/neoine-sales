"""DealRepository 계약: Next Action 기준 행(RK-R1)이 상세·목록·상태 필터·종료 대상 조회에서 같다.

Fake와 SQL(PostgreSQL)에 같은 기대값. 정의는 domain `pick_next_action_basis`(지난 Open 우선,
Due 오름차순·id 내림차순, 없으면 수행일·id 내림차순)이고, Deal 목록 질의와 Action 저장소의
`next_action_basis`가 같은 행을 고른다. 오늘(업무 날짜)은 질의·조회에 `today`로 넘긴다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery
from app.domain.deal_action.value_objects import DealActionId
from tests.factories import date_after, later, make_deal

if TYPE_CHECKING:
    from app.application.ports.deal_repository import DealListItem
    from tests.unit.repositories.deal_case import DealCase

TODAY = date_after(10)  # 아래 Due(NOW+2~4일)는 지난 날짜, NOW+30일은 미래다
LOW, HIGH = DealActionId(2_000_000_001), DealActionId(2_000_000_009)


def _code(number: int) -> str:
    return f"20261016-A{number:03d}"


async def _seed(case: DealCase) -> dict[str, DealActionId]:
    """RK-080·081·083·084와 지난 Open이 없는 Deal. 값은 Deal별 기대 기준 행 id다."""
    expected: dict[str, DealActionId] = {}
    # A001(RK-080): 지난 Open 둘과 더 최근의 미래 Open
    d1 = make_deal(later(5), code=_code(1))
    await case.add(d1)
    await case.add_action(d1, acted_on=date_after(1), next_action="가", due_date=date_after(4))
    b = await case.add_action(d1, acted_on=date_after(2), next_action="나", due_date=date_after(2))
    await case.add_action(d1, acted_on=date_after(9), next_action="다", due_date=date_after(30))
    expected[d1.id.value] = b.id
    # A002(RK-081): Due가 같은 지난 Open은 id가 큰 행(수행일은 보지 않음)
    d2 = make_deal(later(5), code=_code(2))
    await case.add(d2)
    await case.add_action(
        d2, acted_on=date_after(8), entity_id=LOW, next_action="가", due_date=date_after(3)
    )
    high = await case.add_action(
        d2, acted_on=date_after(2), entity_id=HIGH, next_action="나", due_date=date_after(3)
    )
    expected[d2.id.value] = high.id
    # A003(RK-083): Due 오늘 Open과 더 최근에 종료한 행 -> 지난 Open이 없어 최근 행
    d3 = make_deal(later(5), code=_code(3))
    await case.add(d3)
    await case.add_action(d3, acted_on=date_after(1), next_action="오늘", due_date=TODAY)
    done = await case.add_action(
        d3, acted_on=date_after(9), next_action="종료", due_date=date_after(30)
    )
    await case.set_next_action_status(done, "done", later(100))
    expected[d3.id.value] = done.id
    # A004(RK-084): Won Deal도 지난 Open 우선
    d4 = make_deal(later(5), code=_code(4), forecast_key="won", status_key="contract_completed")
    await case.add(d4)
    past = await case.add_action(
        d4, acted_on=date_after(1), next_action="후속", due_date=date_after(3)
    )
    later_done = await case.add_action(
        d4, acted_on=date_after(9), next_action="감사", due_date=date_after(30)
    )
    await case.set_next_action_status(later_done, "done", later(100))
    expected[d4.id.value] = past.id
    # A005: 지난 Open이 없고 가장 최근 행이 not_done
    d5 = make_deal(later(5), code=_code(5))
    await case.add(d5)
    last = await case.add_action(
        d5, acted_on=date_after(9), next_action="미수행", due_date=date_after(30)
    )
    await case.set_next_action_status(last, "not_done", later(100))
    expected[d5.id.value] = last.id
    return expected


async def test_detail_list_and_action_lookup_pick_the_same_basis_row(deal_case: DealCase) -> None:
    """상세·목록 행의 next_action.action_id와 종료 대상 조회가 Deal마다 같은 기준 행이다.

    테스트 코드: RK-085
    """
    # given: 지난 Open 우선·id 동률·Due 오늘·Won·종료만 있는 Deal들
    expected = await _seed(deal_case)

    # when: 같은 오늘로 상세·목록·Action 저장소의 기준 행 조회를 부른다
    listed = {
        item.deal.id.value: item
        for item in await deal_case.deals.search(DealQuery().with_today(TODAY))
    }
    for code, basis_id in expected.items():
        detail: DealListItem = await deal_case.deals.get_item(listed[code].deal.id, today=TODAY)
        target = await deal_case.actions.next_action_basis(detail.deal.id, today=TODAY)

        # then: 세 곳이 모두 기대 기준 행(id)을 가리킨다
        assert detail.next_action is not None
        assert detail.next_action.action_id == basis_id, code
        assert listed[code].next_action is not None
        assert listed[code].next_action.action_id == basis_id, code
        assert target is not None
        assert target.id == basis_id, code


async def test_next_action_status_filter_follows_the_basis_row_status(
    deal_case: DealCase,
) -> None:
    """상태 필터는 그 오늘의 기준 행 상태로 거르고 count도 같다.

    테스트 코드: RK-085
    """
    # given: DL-126 유형의 Deal들. 기준 행 상태는 A001·A002·A004 open, A003 done, A005 not_done
    await _seed(deal_case)

    async def codes(status: NextActionStatusFilter) -> list[str]:
        query = DealQuery(next_action_status=status).with_today(TODAY)
        found = sorted(i.deal.id.value for i in await deal_case.deals.search(query))
        assert await deal_case.deals.count(query) == len(found)
        return found

    # when·then: 상태별로 조회하면 기준 행 상태가 같은 Deal만 나온다
    assert await codes(NextActionStatusFilter.OPEN) == [_code(1), _code(2), _code(4)]
    assert await codes(NextActionStatusFilter.DONE) == [_code(3)]
    assert await codes(NextActionStatusFilter.NOT_DONE) == [_code(5)]
    assert await codes(NextActionStatusFilter.CLOSED) == [_code(3), _code(5)]


async def test_the_basis_changes_with_today_without_any_data_change(deal_case: DealCase) -> None:
    """데이터를 바꾸지 않아도 오늘이 지나 Due가 어제가 되면 다음 조회부터 기준 행이 바뀐다.

    테스트 코드: RK-085
    """
    # given: Due가 오늘인 Open 행 A와 그 뒤 종료한 행 B가 있는 Deal(A003 유형)
    expected = await _seed(deal_case)
    deal = make_deal(code=_code(3))

    # when: 오늘과 하루 뒤에 상세를 조회한다
    on_the_day = await deal_case.deals.get_item(deal.id, today=TODAY)
    next_day = await deal_case.deals.get_item(deal.id, today=date_after(11))

    # then: 오늘은 종료한 행 B, 하루 뒤는 Open 행 A(Due 어제)다
    assert on_the_day.next_action is not None
    assert on_the_day.next_action.action_id == expected[_code(3)]
    assert next_day.next_action is not None
    assert next_day.next_action.text == "오늘"


async def test_search_without_today_is_a_programming_error(deal_case: DealCase) -> None:
    """오늘이 없는 search는 ValueError다(기준 행을 고를 수 없다).

    테스트 코드: RK-085
    """
    # given: Deal 하나
    await deal_case.add(make_deal(later(5), code=_code(1)))

    # when·then: today 없이 저장소 자체를 검색하면 ValueError다
    with pytest.raises(ValueError):  # noqa: PT011 - 프로그래밍 오류
        await deal_case.deals.raw.search(DealQuery())


async def test_count_needs_today_only_with_the_next_action_status_filter(
    deal_case: DealCase,
) -> None:
    """count는 next_action_status가 있을 때만 today가 필요하다(Dashboard count는 영향 없음).

    테스트 코드: RK-085
    """
    # given: Deal 하나
    await deal_case.add(make_deal(later(5), code=_code(1)))

    # when·then: 상태 필터 없는 count는 today 없이도 센다
    assert await deal_case.deals.raw.count(DealQuery()) == 1
    # when·then: 상태 필터가 있는데 today가 없으면 ValueError다
    with pytest.raises(ValueError):  # noqa: PT011 - 프로그래밍 오류
        await deal_case.deals.raw.count(DealQuery(next_action_status=NextActionStatusFilter.OPEN))
