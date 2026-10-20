"""DealActionRepository 계약(AC-1·2·5·7·8·12·18): 비어 있을 수 있는 필드, Next Action 상태.

Fake와 SQL(PostgreSQL)에 같은 테스트.
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import (
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.deal_action.next_action_status import NextActionState, NextActionStatus
from tests.factories import NOW, later, make_action_content, make_deal_action

if TYPE_CHECKING:
    from tests.unit.repositories.deal_action_case import Case


async def test_progress_only_action_round_trips_with_null_next_action_fields(
    action_case: Case,
) -> None:
    action = make_deal_action(later(5), action="진행만", next_action="", memo="")
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.action == "진행만"
    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None


async def test_next_only_action_round_trips_as_open(action_case: Case) -> None:
    action = make_deal_action(later(5), action="", next_action="견적", due_date=date(2026, 3, 1))
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.action is None
    assert stored.content.next_action == "견적"
    assert stored.content.due_date == date(2026, 3, 1)
    assert stored.next_action_state == NextActionState.open()


async def test_update_persists_a_closed_status_and_closed_time(action_case: Case) -> None:
    action = make_deal_action(later(5), memo="기존")
    await action_case.add(action)

    action.change_next_action_status(NextActionStatus.DONE, "끝남", later(50))
    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.next_action_state == NextActionState(
        status=NextActionStatus.DONE, closed_at=later(50)
    )
    assert stored.content.memo == "기존\n끝남"
    assert stored.updated_at == later(50)
    assert stored.acted_at == later(5)


async def test_update_reopening_clears_the_closed_time(action_case: Case) -> None:
    action = make_deal_action(later(5))
    await action_case.add(action)
    action.change_next_action_status(NextActionStatus.NOT_DONE, "", later(50))
    await action_case.repository.update(action)

    action.change_next_action_status(NextActionStatus.OPEN, "", later(60))
    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.next_action_state == NextActionState.open()


async def test_update_removing_the_next_action_clears_content_and_state(
    action_case: Case,
) -> None:
    action = make_deal_action(later(5))
    await action_case.add(action)
    action.change_next_action_status(NextActionStatus.DONE, "", later(50))
    action.revise(
        make_action_content(action_type=action.content.action_type, next_action="", due_date=None),
        later(60),
    )
    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.next_action is None
    assert stored.content.due_date is None
    assert stored.next_action_state is None


async def test_update_adding_a_next_action_stores_it_as_open(action_case: Case) -> None:
    action = make_deal_action(later(5), next_action="")
    await action_case.add(action)
    action.revise(
        make_action_content(
            action_type=action.content.action_type,
            next_action="새 계획",
            due_date=date(2026, 4, 1),
        ),
        later(60),
    )
    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.next_action == "새 계획"
    assert stored.next_action_state == NextActionState.open()


async def _seed_states(action_case: Case) -> None:
    """open(첫 계획), done(둘째), not_done(셋째), Next Action 없음(넷째)."""
    rows = [("첫", None), ("둘", "done"), ("셋", "not_done"), ("넷", "none")]
    for day, (name, state) in enumerate(rows):
        action = make_deal_action(
            acted_at=NOW + timedelta(days=day),
            action=name,
            next_action="" if state == "none" else f"{name} 계획",
        )
        await action_case.add(action)
        if state in ("done", "not_done"):
            action.change_next_action_status(NextActionStatus(state), "", NOW + timedelta(days=9))
            await action_case.repository.update(action)


async def test_action_search_filters_by_status_including_closed(action_case: Case) -> None:
    await _seed_states(action_case)
    sort = DealActionSort.ACTED_AT_ASC

    assert await action_case.search(next_action_status=NextActionStatusFilter.OPEN, sort=sort) == [
        "첫"
    ]
    assert await action_case.search(next_action_status=NextActionStatusFilter.DONE, sort=sort) == [
        "둘"
    ]
    assert await action_case.search(
        next_action_status=NextActionStatusFilter.NOT_DONE, sort=sort
    ) == ["셋"]
    assert await action_case.search(
        next_action_status=NextActionStatusFilter.CLOSED, sort=sort
    ) == ["둘", "셋"]


async def test_action_search_status_filter_excludes_rows_without_next_action(
    action_case: Case,
) -> None:
    await _seed_states(action_case)

    for status in NextActionStatusFilter:
        assert "넷" not in await action_case.search(next_action_status=status)
    assert "넷" in await action_case.search()


async def test_due_sort_puts_missing_due_last(action_case: Case) -> None:
    for day, (name, due) in enumerate(
        [("없음", None), ("늦음", date(2026, 3, 1)), ("빠름", date(2026, 2, 1))]
    ):
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(days=day),
                action=name,
                next_action="" if due is None else f"{name} 계획",
                due_date=due,
            )
        )

    assert await action_case.search(sort=DealActionSort.DUE_DATE_ASC) == ["빠름", "늦음", "없음"]


async def test_keyword_search_skips_missing_fields_without_error(action_case: Case) -> None:
    await action_case.add(make_deal_action(acted_at=NOW, action="", next_action="견적 전달"))
    await action_case.add(
        make_deal_action(acted_at=NOW + timedelta(days=1), action="견적 통화", next_action="")
    )

    found = await action_case.found(keyword="견적", sort=DealActionSort.ACTED_AT_ASC)

    assert [a.content.action for a in found] == [None, "견적 통화"]
