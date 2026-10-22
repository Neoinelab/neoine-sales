"""DealActionRepository 헤더 정렬 계약(AC7~AC10): Fake와 SQL 구현에 같은 테스트.

담당자·유형은 대소문자 무시 코드 포인트 순, 상태는 Open -> done -> not_done, 빈 값은 방향과 관계없이
맨 뒤, 동률은 수행일시 내림차순 -> id 오름차순(방향을 바꿔도 뒤집히지 않는다).
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import DealActionSort
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import NOW, make_deal_action
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_action_case import Case


async def _add_due(action_case: Case, rows: list[tuple[str, date | None, int]]) -> None:
    for name, due, minutes in rows:
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(minutes=minutes),
                action=name,
                next_action="" if due is None else f"{name} 계획",
                due_date=due,
            )
        )


async def test_due_date_desc_puts_latest_first_and_missing_due_last(action_case: Case) -> None:
    await _add_due(
        action_case,
        [("빠름", date(2026, 2, 1), 0), ("없음", None, 1), ("늦음", date(2026, 2, 10), 2)],
    )

    assert await action_case.search(sort=DealActionSort.DUE_DATE_DESC) == ["늦음", "빠름", "없음"]


async def test_due_date_desc_breaks_ties_by_latest_acted_at_then_id(action_case: Case) -> None:
    due = date(2026, 2, 10)
    await _add_due(
        action_case,
        [
            ("오래됨", due, 0),
            ("최신", due, 10),
            ("같은 시각 먼저", due, 5),
            ("같은 시각 나중", due, 5),
        ],
    )

    assert await action_case.search(sort=DealActionSort.DUE_DATE_DESC) == [
        "최신",
        "같은 시각 먼저",
        "같은 시각 나중",
        "오래됨",
    ]


async def _add_by_actor(action_case: Case, rows: list[tuple[str, str | None, str]]) -> None:
    """(login_id, 표시 이름, 진행사항). 수행 시각은 등록 순서대로 1분씩 늦다."""
    for minute, (login, display, name) in enumerate(rows):
        user_id = uid(login)
        await action_case.ensure_actor_named(user_id, display, login_id=login)
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(minutes=minute), action=name, actor_user_id=user_id
            )
        )


async def test_actor_sort_uses_display_name_case_insensitively(action_case: Case) -> None:
    await _add_by_actor(
        action_case,
        [("s_bob", "bob", "밥"), ("s_alice", "Alice", "앨리스"), ("s_carol", "carol", "캐롤")],
    )

    assert await action_case.search(sort=DealActionSort.ACTOR_ASC) == ["앨리스", "밥", "캐롤"]
    assert await action_case.search(sort=DealActionSort.ACTOR_DESC) == ["캐롤", "밥", "앨리스"]


async def test_actor_sort_falls_back_to_login_id_when_display_name_is_empty(
    action_case: Case,
) -> None:
    await _add_by_actor(action_case, [("dave", None, "데이브"), ("s_carol2", "Carol", "캐롤")])

    assert await action_case.search(sort=DealActionSort.ACTOR_ASC) == ["캐롤", "데이브"]
    assert await action_case.search(sort=DealActionSort.ACTOR_DESC) == ["데이브", "캐롤"]


async def test_actor_sort_includes_resigned_users_by_their_name(action_case: Case) -> None:
    await _add_by_actor(action_case, [("s_bella", "Bella", "벨라"), ("s_aaron", "Aaron", "아론")])
    await action_case.resign_actor(uid("s_aaron"))

    assert await action_case.search(sort=DealActionSort.ACTOR_ASC) == ["아론", "벨라"]


async def test_action_type_sort_uses_current_type_name_case_insensitively(
    action_case: Case,
) -> None:
    for minute, (type_name, name) in enumerate(
        [("통화", "통화함"), ("Beta", "베타"), ("미팅", "미팅함"), ("alpha", "알파")]
    ):
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(minutes=minute), action=name, action_type=type_name
            )
        )

    assert await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC) == [
        "알파",
        "베타",
        "미팅함",
        "통화함",
    ]
    assert await action_case.search(sort=DealActionSort.ACTION_TYPE_DESC) == [
        "통화함",
        "미팅함",
        "베타",
        "알파",
    ]


async def test_action_type_sort_follows_renamed_type(action_case: Case) -> None:
    for minute, (type_name, name) in enumerate([("가나", "A"), ("다라", "B")]):
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(minutes=minute), action=name, action_type=type_name
            )
        )
    assert await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC) == ["A", "B"]

    first = next(t for t in await action_case.action_types.list() if t.name == "가나")
    first.rename("힣 마지막", NOW + timedelta(days=1))
    await action_case.action_types.update(first)

    assert await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC) == ["B", "A"]


async def _seed_statuses(action_case: Case) -> None:
    """수행 순서: 미수행 종료, Next Action 없음, 수행 종료, Open."""
    rows = [("미수행", "not_done"), ("없음", None), ("수행", "done"), ("열림", "open")]
    for minute, (name, state) in enumerate(rows):
        action = make_deal_action(
            acted_at=NOW + timedelta(minutes=minute),
            action=name,
            next_action="" if state is None else f"{name} 계획",
        )
        await action_case.add(action)
        if state in ("done", "not_done"):
            action.change_next_action_status(NextActionStatus(state), "", NOW + timedelta(days=9))
            await action_case.repository.update(action)


async def test_next_action_status_asc_orders_open_done_not_done_with_missing_last(
    action_case: Case,
) -> None:
    await _seed_statuses(action_case)

    assert await action_case.search(sort=DealActionSort.NEXT_ACTION_STATUS_ASC) == [
        "열림",
        "수행",
        "미수행",
        "없음",
    ]


async def test_next_action_status_desc_reverses_but_keeps_missing_last(
    action_case: Case,
) -> None:
    await _seed_statuses(action_case)

    assert await action_case.search(sort=DealActionSort.NEXT_ACTION_STATUS_DESC) == [
        "미수행",
        "수행",
        "열림",
        "없음",
    ]


async def test_non_acted_sorts_break_ties_by_latest_acted_at_then_id(action_case: Case) -> None:
    same_actor = uid("tie_actor")
    await action_case.ensure_actor_named(same_actor, "Tie", login_id="tie_actor")
    for name, minute in [("오래됨", 0), ("최신", 10), ("중간 먼저", 5), ("중간 나중", 5)]:
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(minutes=minute), action=name, actor_user_id=same_actor
            )
        )
    expected = ["최신", "중간 먼저", "중간 나중", "오래됨"]

    assert await action_case.search(sort=DealActionSort.ACTOR_ASC) == expected
    assert await action_case.search(sort=DealActionSort.ACTOR_DESC) == expected
