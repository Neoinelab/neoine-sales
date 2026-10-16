"""DealActionRepository 검색 계약(필터·정렬·날짜·전부 반환): Fake와 SQL 구현에 같은 테스트."""

from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_action_repository import DealActionSort
from app.domain.deal_action.value_objects import ActionType
from tests.factories import NOW, make_deal_action, make_deal_code
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.unit.repositories.deal_action_case import Case


async def _seed(action_case: Case) -> None:
    rows = [
        (ActionType.CALL, "첫 통화", "견적서 준비", "예산 문의 100%", "kim", 0, date(2026, 2, 10)),
        (ActionType.MEETING, "킥오프 미팅", "요구사항 정리", "일정", "park", 1, date(2026, 2, 1)),
        (ActionType.MEETING, "최종 미팅", "계약서 초안", "조건", "kim", 2, date(2026, 2, 10)),
    ]
    for action_type, action, next_action, memo, actor, day, due in rows:
        await action_case.add(
            make_deal_action(
                acted_at=NOW + timedelta(days=day),
                action_type=action_type,
                action=action,
                next_action=next_action,
                memo=memo,
                actor_user_id=uid(actor),
                due_date=due,
            )
        )


async def test_search_orders_by_latest_acted_at_first_by_default(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search() == ["최종 미팅", "킥오프 미팅", "첫 통화"]
    assert await action_case.search(sort=DealActionSort.ACTED_AT_DESC) == [
        "최종 미팅",
        "킥오프 미팅",
        "첫 통화",
    ]


async def test_search_can_order_by_oldest_acted_at_first(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search(sort=DealActionSort.ACTED_AT_ASC) == [
        "첫 통화",
        "킥오프 미팅",
        "최종 미팅",
    ]


async def test_search_by_due_date_breaks_ties_by_latest_acted_at(action_case: Case) -> None:
    await _seed(action_case)

    # 기한 02-01 -> 킥오프, 02-10 동률은 수행 시각 최신순: 최종 -> 첫 통화
    assert await action_case.search(sort=DealActionSort.DUE_DATE_ASC) == [
        "킥오프 미팅",
        "최종 미팅",
        "첫 통화",
    ]


async def test_search_filters_combine_with_and(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search(action_type=ActionType.MEETING, actor_user_id=uid("kim")) == [
        "최종 미팅"
    ]
    assert await action_case.search(actor_user_id=uid("park")) == ["킥오프 미팅"]
    assert await action_case.search(actor_user_id=uid("nobody")) == []


async def test_search_keyword_matches_the_three_text_fields_ignoring_case(
    action_case: Case,
) -> None:
    await _seed(action_case)
    await action_case.add(make_deal_action(NOW + timedelta(days=9), action="Kickoff Memo"))

    assert await action_case.search(keyword="킥오프") == ["킥오프 미팅"]  # action
    assert await action_case.search(keyword="계약서") == ["최종 미팅"]  # next_action
    assert await action_case.search(keyword="예산") == ["첫 통화"]  # memo
    assert await action_case.search(keyword="KICKOFF") == ["Kickoff Memo"]
    assert await action_case.search(keyword="kickoff") == ["Kickoff Memo"]


async def test_search_keyword_treats_wildcards_literally(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search(keyword="100%") == ["첫 통화"]
    assert await action_case.search(keyword="%") == ["첫 통화"]
    assert await action_case.search(keyword="_") == []


async def test_search_keyword_finds_text_deep_inside_a_very_long_memo(action_case: Case) -> None:
    long_memo = "가" * 15_000 + "깊은키워드" + "나" * 5_000
    await action_case.add(make_deal_action(NOW, action="긴 메모", memo=long_memo))

    assert await action_case.search(keyword="깊은키워드") == ["긴 메모"]


async def test_search_due_range_is_inclusive_on_both_ends(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search(due_from=date(2026, 2, 1), due_to=date(2026, 2, 10)) == [
        "최종 미팅",
        "킥오프 미팅",
        "첫 통화",
    ]
    assert await action_case.search(due_from=date(2026, 2, 10)) == ["최종 미팅", "첫 통화"]
    assert await action_case.search(due_to=date(2026, 2, 1)) == ["킥오프 미팅"]
    assert await action_case.search(due_from=date(2026, 2, 11)) == []


async def test_search_acted_date_covers_the_local_day_on_both_ends(
    action_case: Case, local_tz: Callable[[str], None]
) -> None:
    local_tz("Asia/Seoul")
    moments = {  # 로컬(KST) 경계 직전·직후
        "전날 23:59": datetime(2026, 10, 15, 14, 59, tzinfo=UTC),
        "당일 00:00": datetime(2026, 10, 15, 15, 0, tzinfo=UTC),
        "당일 23:59": datetime(2026, 10, 16, 14, 59, tzinfo=UTC),
        "다음날 00:00": datetime(2026, 10, 16, 15, 0, tzinfo=UTC),
    }
    for name, moment in moments.items():
        await action_case.add(make_deal_action(moment, action=name))

    day = date(2026, 10, 16)
    assert await action_case.search(acted_from=day, acted_to=day) == ["당일 23:59", "당일 00:00"]
    assert await action_case.search(acted_from=day) == ["다음날 00:00", "당일 23:59", "당일 00:00"]
    assert await action_case.search(acted_to=day) == ["당일 23:59", "당일 00:00", "전날 23:59"]


async def test_search_returns_every_match_without_a_page_limit(action_case: Case) -> None:
    for number in range(25):
        await action_case.add(
            make_deal_action(NOW + timedelta(minutes=number), action=f"활동 {number:02d}")
        )

    assert len(await action_case.search()) == 25


async def test_search_is_scoped_to_the_deal(action_case: Case) -> None:
    await _seed(action_case)
    other = make_deal_action(NOW, action="다른 딜", deal_code=make_deal_code("B002"))
    await action_case.add(other)

    assert await action_case.search(deal_code=other.deal_code) == ["다른 딜"]
    assert "다른 딜" not in await action_case.search()
