"""DealActionRepository 헤더 정렬 계약: Fake와 SQL 구현에 같은 테스트.

담당자·유형은 대소문자 무시 코드 포인트 순, 상태는 Open -> done -> not_done, 빈 값은 방향과 관계없이
맨 뒤, 동률은 수행일 내림차순 -> id 내림차순(방향을 바꿔도 뒤집히지 않는다, AC-R43).
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
    for name, due, days_later in rows:
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=days_later),
                action=name,
                next_action="" if due is None else f"{name} 계획",
                due_date=due,
            )
        )


async def test_due_date_desc_puts_latest_first_and_missing_due_last(action_case: Case) -> None:
    """Due 내림차순은 늦은 기한부터 나오고 기한이 없는 것은 맨 뒤에 둔다."""
    # given: 기한이 빠른·늦은·없는 Action 3건
    await _add_due(
        action_case,
        [("빠름", date(2026, 2, 1), 0), ("없음", None, 1), ("늦음", date(2026, 2, 10), 2)],
    )

    # when: Due 내림차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.DUE_DATE_DESC)
    # then: 늦은 기한, 빠른 기한, 기한 없음 순이다
    assert found == ["늦음", "빠름", "없음"]


async def test_due_date_desc_breaks_ties_by_latest_acted_on_then_id(action_case: Case) -> None:
    """Due 내림차순에서 기한이 같으면 수행일 최신순, 그다음 id 내림차순(나중 등록이 앞)이다.

    테스트 코드: NA-069
    """
    # given: 기한이 같고 수행일이 다르거나 같은 Action 4건
    due = date(2026, 2, 10)
    await _add_due(
        action_case,
        [
            ("오래됨", due, 0),
            ("최신", due, 10),
            ("같은 날 먼저", due, 5),
            ("같은 날 나중", due, 5),
        ],
    )

    # when: Due 내림차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.DUE_DATE_DESC)
    # then: 수행일 최신순이고, 같은 날은 나중에 등록한 것이 앞이다
    assert found == [
        "최신",
        "같은 날 나중",
        "같은 날 먼저",
        "오래됨",
    ]


async def _add_by_actor(action_case: Case, rows: list[tuple[str, str | None, str]]) -> None:
    """(login_id, 표시 이름, 진행사항). 수행일은 등록 순서대로 하루씩 늦다."""
    for days_later, (login, display, name) in enumerate(rows):
        user_id = uid(login)
        await action_case.ensure_actor_named(user_id, display, login_id=login)
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=days_later), action=name, actor_user_id=user_id
            )
        )


async def test_actor_sort_uses_display_name_case_insensitively(action_case: Case) -> None:
    """수행자 정렬은 표시 이름을 대소문자 무시로 비교한다."""
    # given: 표시 이름이 bob·Alice·carol인 수행자의 Action 3건
    await _add_by_actor(
        action_case,
        [("s_bob", "bob", "밥"), ("s_alice", "Alice", "앨리스"), ("s_carol", "carol", "캐롤")],
    )

    # when: 수행자 오름차순으로 검색한다
    ascending = await action_case.search(sort=DealActionSort.ACTOR_ASC)
    # then: Alice, bob, carol 순이다
    assert ascending == ["앨리스", "밥", "캐롤"]
    # when: 수행자 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTOR_DESC)
    # then: carol, bob, Alice 순이다
    assert descending == ["캐롤", "밥", "앨리스"]


async def test_actor_sort_falls_back_to_login_id_when_display_name_is_empty(
    action_case: Case,
) -> None:
    """표시 이름이 비어 있으면 수행자 정렬은 로그인 아이디를 쓴다."""
    # given: 표시 이름이 없는 수행자(dave)와 Carol의 Action
    await _add_by_actor(action_case, [("dave", None, "데이브"), ("s_carol2", "Carol", "캐롤")])

    # when: 수행자 오름차순으로 검색한다
    ascending = await action_case.search(sort=DealActionSort.ACTOR_ASC)
    # then: Carol, dave 순이다
    assert ascending == ["캐롤", "데이브"]
    # when: 수행자 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTOR_DESC)
    # then: dave, Carol 순이다
    assert descending == ["데이브", "캐롤"]


async def test_actor_sort_includes_resigned_users_by_their_name(action_case: Case) -> None:
    """퇴사한 수행자도 이름으로 정렬에 포함된다."""
    # given: 수행자 Bella와 Aaron의 Action, Aaron은 퇴사 처리
    await _add_by_actor(action_case, [("s_bella", "Bella", "벨라"), ("s_aaron", "Aaron", "아론")])
    await action_case.resign_actor(uid("s_aaron"))

    # when: 수행자 오름차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.ACTOR_ASC)
    # then: 퇴사자 Aaron도 이름 순서대로 앞에 나온다
    assert found == ["아론", "벨라"]


async def test_action_type_sort_uses_current_type_name_case_insensitively(
    action_case: Case,
) -> None:
    """유형 정렬은 현재 유형 이름을 대소문자 무시로 비교한다."""
    # given: 유형이 통화·Beta·미팅·alpha인 Action 4건
    for days_later, (type_name, name) in enumerate(
        [("통화", "통화함"), ("Beta", "베타"), ("미팅", "미팅함"), ("alpha", "알파")]
    ):
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=days_later), action=name, action_type=type_name
            )
        )

    # when: 유형 오름차순으로 검색한다
    ascending = await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC)
    # then: alpha, Beta, 미팅, 통화 순이다
    assert ascending == [
        "알파",
        "베타",
        "미팅함",
        "통화함",
    ]
    # when: 유형 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTION_TYPE_DESC)
    # then: 통화, 미팅, Beta, alpha 순이다
    assert descending == [
        "통화함",
        "미팅함",
        "베타",
        "알파",
    ]


async def test_action_type_sort_follows_renamed_type(action_case: Case) -> None:
    """유형 이름을 바꾸면 유형 정렬 순서도 바뀐다."""
    # given: 유형이 "가나"·"다라"인 Action 2건
    for days_later, (type_name, name) in enumerate([("가나", "A"), ("다라", "B")]):
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=days_later), action=name, action_type=type_name
            )
        )
    # when: 이름을 바꾸기 전에 유형 오름차순으로 검색한다
    before = await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC)
    # then: 가나(A), 다라(B) 순이다
    assert before == ["A", "B"]

    # given: "가나" 유형의 이름을 "힣 마지막"으로 바꾼다
    first = next(t for t in await action_case.action_types.list() if t.name == "가나")
    first.rename("힣 마지막", NOW + timedelta(days=1))
    await action_case.action_types.update(first)

    # when: 이름을 바꾼 뒤 유형 오름차순으로 검색한다
    after = await action_case.search(sort=DealActionSort.ACTION_TYPE_ASC)
    # then: B, A 순으로 바뀐다
    assert after == ["B", "A"]


async def _seed_statuses(action_case: Case) -> None:
    """수행 순서: 미수행 종료, Next Action 없음, 수행 종료, Open."""
    rows = [("미수행", "not_done"), ("없음", None), ("수행", "done"), ("열림", "open")]
    for days_later, (name, state) in enumerate(rows):
        action = make_deal_action(
            now=NOW + timedelta(days=days_later),
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
    """Next Action 상태 오름차순은 Open, 수행, 미수행 순이고 Next Action이 없는 것은 맨 뒤다."""
    # given: 미수행·Next Action 없음·수행·Open 상태의 Action 4건
    await _seed_statuses(action_case)

    # when: Next Action 상태 오름차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.NEXT_ACTION_STATUS_ASC)
    # then: 열림, 수행, 미수행, 없음 순이다
    assert found == [
        "열림",
        "수행",
        "미수행",
        "없음",
    ]


async def test_next_action_status_desc_reverses_but_keeps_missing_last(
    action_case: Case,
) -> None:
    """Next Action 상태 내림차순은 순서를 뒤집되 Next Action이 없는 것은 계속 맨 뒤다."""
    # given: 미수행·Next Action 없음·수행·Open 상태의 Action 4건
    await _seed_statuses(action_case)

    # when: Next Action 상태 내림차순으로 검색한다
    found = await action_case.search(sort=DealActionSort.NEXT_ACTION_STATUS_DESC)
    # then: 미수행, 수행, 열림 순이고 없음은 맨 뒤다
    assert found == [
        "미수행",
        "수행",
        "열림",
        "없음",
    ]


async def test_non_acted_sorts_break_ties_by_latest_acted_on_then_id(action_case: Case) -> None:
    """수행일 외 정렬에서 값이 같으면 수행일 최신순, 그다음 id 내림차순(나중 등록이 앞)이다.

    테스트 코드: NA-069
    """
    # given: 같은 수행자가 수행일이 다르거나 같게 남긴 Action 4건
    same_actor = uid("tie_actor")
    await action_case.ensure_actor_named(same_actor, "Tie", login_id="tie_actor")
    for name, days_later in [("오래됨", 0), ("최신", 10), ("중간 먼저", 5), ("중간 나중", 5)]:
        await action_case.add(
            make_deal_action(
                now=NOW + timedelta(days=days_later), action=name, actor_user_id=same_actor
            )
        )
    expected = ["최신", "중간 나중", "중간 먼저", "오래됨"]

    # when: 수행자 오름차순으로 검색한다
    ascending = await action_case.search(sort=DealActionSort.ACTOR_ASC)
    # then: 수행일 최신순이고 같은 날은 나중에 등록한 것이 앞이다
    assert ascending == expected
    # when: 수행자 내림차순으로 검색한다
    descending = await action_case.search(sort=DealActionSort.ACTOR_DESC)
    # then: 방향을 바꿔도 같은 순서다
    assert descending == expected
