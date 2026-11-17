"""DealActionRepository 계약: 비어 있을 수 있는 필드, Next Action 상태.

Fake와 SQL(PostgreSQL)에 같은 테스트.
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import (
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from tests.factories import NOW, date_after, later, make_action_content, make_deal_action

if TYPE_CHECKING:
    from tests.unit.repositories.deal_action_case import Case


async def test_progress_only_action_round_trips_with_null_next_action_fields(
    action_case: Case,
) -> None:
    """진행사항만 있는 Action은 Next Action 필드가 비어 있는 채로 저장·조회된다."""
    # given: 진행사항만 있는 Action
    action = make_deal_action(later(5), action="진행만", next_action="")
    # when: 저장한다
    await action_case.add(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)

    # then: Next Action·기한·상태가 모두 비어 있다
    assert stored.content.action == "진행만"
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None


async def test_next_only_action_round_trips_as_open(action_case: Case) -> None:
    """Next Action만 있는 Action은 진행사항이 비고 상태는 Open으로 저장·조회된다."""
    # given: Next Action과 기한만 있는 Action
    action = make_deal_action(later(5), action="", next_action="견적", due_date=date(2026, 3, 1))
    # when: 저장한다
    await action_case.add(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)

    # then: 진행사항은 비고 Next Action·기한이 있으며 상태는 Open이다
    assert stored.content.action is None
    assert stored.content.next_action == "견적"
    assert stored.content.due_date == date(2026, 3, 1)
    assert stored.next_action_state == NextActionState.open()


async def test_update_persists_a_closed_status_and_closed_date(action_case: Case) -> None:
    """종료 상태 변경을 저장하면 상태·종료일·수정 시각이 남고 내용은 그대로다."""
    # given: 저장된 Action
    action = make_deal_action(later(5))
    await action_case.add(action)
    content = action.content

    # when: 수행 종료로 바꾸고(종료 Comment는 별도 엔티티) 저장한다
    action.change_next_action_status(NextActionStatus.DONE, "끝남", later(50))
    await action_case.repository.update(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 상태와 종료일이 남고 내용·수행일은 그대로다
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.DONE, closed_on=date_after(0)
    )
    assert stored.content == content
    assert stored.updated_at == later(50)
    assert stored.acted_on == date_after(0)


async def test_update_reopening_clears_the_closed_date(action_case: Case) -> None:
    """다시 Open으로 바꾸면 종료일이 지워진다."""
    # given: 미수행으로 종료한 Action
    action = make_deal_action(later(5))
    await action_case.add(action)
    action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(50))
    await action_case.repository.update(action)

    # when: 다시 Open으로 바꿔 저장한다
    action.change_next_action_status(NextActionStatus.OPEN, "", later(60))
    await action_case.repository.update(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 상태가 Open이고 종료일이 없다
    assert stored.next_action_state == NextActionState.open()


async def test_update_removing_the_next_action_clears_content_and_state(
    action_case: Case,
) -> None:
    """Next Action을 지우고 저장하면 내용·기한·상태가 모두 비워진다."""
    # given: 수행 종료한 Next Action이 있는 Action
    action = make_deal_action(later(5))
    await action_case.add(action)
    action.change_next_action_status(NextActionStatus.DONE, "", later(50))
    # when: Next Action을 비워 수정해 저장한다
    action.revise(
        make_action_content(action_type=action.content.action_type, next_action="", due_date=None),
        later(60),
    )
    await action_case.repository.update(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)

    # then: Next Action·기한·상태가 모두 비어 있다
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None


async def test_update_adding_a_next_action_stores_it_as_open(action_case: Case) -> None:
    """Next Action을 새로 넣고 저장하면 Open 상태로 저장된다."""
    # given: Next Action이 없는 Action
    action = make_deal_action(later(5), next_action="")
    await action_case.add(action)
    # when: Next Action과 기한을 넣어 수정해 저장한다
    action.revise(
        make_action_content(
            action_type=action.content.action_type,
            next_action="새 계획",
            due_date=date(2026, 4, 1),
        ),
        later(60),
    )
    await action_case.repository.update(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)

    # then: Next Action이 있고 상태는 Open이다
    assert stored.content.next_action == "새 계획"
    assert stored.next_action_state == NextActionState.open()


async def _seed_states(action_case: Case) -> None:
    """open(첫 계획), done(둘째), not_done(셋째), Next Action 없음(넷째)."""
    rows = [("첫", None), ("둘", "done"), ("셋", "not_done"), ("넷", "none")]
    for day, (name, state) in enumerate(rows):
        action = make_deal_action(
            now=NOW + timedelta(days=day),
            action=name,
            next_action="" if state == "none" else f"{name} 계획",
        )
        await action_case.add(action)
        if state in ("done", "not_done"):
            action.change_next_action_status(NextActionStatus(state), "", NOW + timedelta(days=9))
            await action_case.repository.update(action)


async def test_action_search_filters_by_status_including_closed(action_case: Case) -> None:
    """Next Action 상태로 검색하면 상태별로 걸러지고 closed는 수행·미수행을 함께 찾는다."""
    # given: Open·수행·미수행·Next Action 없음의 Action 4건
    await _seed_states(action_case)
    sort = DealActionSort.ACTED_AT_ASC

    # when: Open으로 검색한다
    opened = await action_case.search(next_action_status=NextActionStatusFilter.OPEN, sort=sort)
    # then: Open인 것만 나온다
    assert opened == ["첫"]
    # when: 수행으로 검색한다
    done = await action_case.search(next_action_status=NextActionStatusFilter.DONE, sort=sort)
    # then: 수행한 것만 나온다
    assert done == ["둘"]
    # when: 미수행으로 검색한다
    not_done = await action_case.search(
        next_action_status=NextActionStatusFilter.NOT_DONE, sort=sort
    )
    # then: 미수행인 것만 나온다
    assert not_done == ["셋"]
    # when: closed로 검색한다
    closed = await action_case.search(next_action_status=NextActionStatusFilter.CLOSED, sort=sort)
    # then: 수행과 미수행이 함께 나온다
    assert closed == ["둘", "셋"]


async def test_action_search_status_filter_excludes_rows_without_next_action(
    action_case: Case,
) -> None:
    """상태 필터는 Next Action이 없는 Action을 제외하고, 필터가 없으면 포함한다."""
    # given: Next Action이 없는 Action을 포함한 4건
    await _seed_states(action_case)

    # when: 상태 필터마다, 그리고 필터 없이 검색한다
    by_status = {
        status: await action_case.search(next_action_status=status)
        for status in NextActionStatusFilter
    }
    unfiltered = await action_case.search()
    # then: 어느 상태 필터에도 Next Action 없는 Action은 나오지 않고, 필터 없이는 나온다
    assert all("넷" not in found for found in by_status.values())
    assert "넷" in unfiltered


async def test_due_sort_puts_missing_due_last(action_case: Case) -> None:
    """Due 오름차순에서 기한이 없는 Action은 맨 뒤에 둔다."""
    # given: 기한이 없음·늦음·빠름인 Action 3건
    for day, (name, due) in enumerate(
        [("없음", None), ("늦음", date(2026, 3, 1)), ("빠름", date(2026, 2, 1))]
    ):
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=day),
                action=name,
                next_action="" if due is None else f"{name} 계획",
                due_date=due,
            )
        )

    # when: Due 오름차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.DUE_DATE_ASC)
    # then: 빠름, 늦음, 없음 순이다
    assert found == ["빠름", "늦음", "없음"]


async def test_keyword_search_skips_missing_fields_without_error(action_case: Case) -> None:
    """키워드 검색은 비어 있는 필드가 있어도 오류 없이 찾는다."""
    # given: 진행사항이 없는 Action과 Next Action이 없는 Action
    await action_case.add(make_deal_action(now=NOW, action="", next_action="견적 전달"))
    await action_case.add(
        make_deal_action(now=NOW + timedelta(days=1), action="견적 통화", next_action="")
    )

    # when: 두 Action에 모두 있는 키워드로 검색한다
    found = await action_case.found(keyword="견적", sort=DealActionSort.ACTED_AT_ASC)

    # then: 두 Action이 모두 나온다
    assert [a.content.action for a in found] == [None, "견적 통화"]
