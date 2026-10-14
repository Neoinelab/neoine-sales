"""DealActionRepository 검색 계약(필터·정렬·키워드): Fake와 SQL 구현에 같은 테스트를 적용한다."""

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_action_repository import DealActionSort
from app.domain.common.errors import InvalidValueError
from app.domain.deal_action.value_objects import ActionType
from tests.factories import NOW, later, make_deal_action
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.contracts.deal_action_case import Case


async def _seed(action_case: Case) -> None:
    rows = [
        (
            ActionType.CALL,
            "첫 통화",
            "견적서 준비",
            "예산 문의 100%",
            uid("kim"),
            0,
            date(2026, 2, 10),
        ),
        (
            ActionType.MEETING,
            "킥오프 미팅",
            "요구사항 정리",
            "일정",
            uid("park"),
            1,
            date(2026, 2, 1),
        ),
        (ActionType.MEETING, "최종 미팅", "계약서 초안", "조건", uid("kim"), 2, date(2026, 2, 10)),
    ]
    for action_type, action, next_action, memo, actor, day, due in rows:
        await action_case.add(
            make_deal_action(
                later(day),
                action_type=action_type,
                action=action,
                next_action=next_action,
                memo=memo,
                actor_user_id=actor,
                acted_at=NOW + timedelta(days=day),
                due_date=due,
            )
        )


async def test_search_orders_by_latest_activity_first(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search() == ["최종 미팅", "킥오프 미팅", "첫 통화"]


async def test_search_filters(action_case: Case) -> None:
    await _seed(action_case)

    assert await action_case.search(action_type=ActionType.MEETING, actor_user_id=uid("kim")) == [
        "최종 미팅"
    ]
    assert await action_case.search(actor_user_id=uid("park")) == ["킥오프 미팅"]
    assert await action_case.search(actor_user_id=uid("nobody")) == []
    assert await action_case.search(keyword="KICKOFF") == []
    assert await action_case.search(keyword="요구") == ["킥오프 미팅"]
    assert await action_case.search(keyword="100%") == ["첫 통화"]
    assert await action_case.search(keyword="_") == []


async def test_search_keyword_matches_action_next_action_and_memo(action_case: Case) -> None:
    await _seed(action_case)
    await action_case.add_legacy(action="레거시", memo="특이 메모")

    assert await action_case.search(keyword="킥오프") == ["킥오프 미팅"]  # action
    assert await action_case.search(keyword="계약서") == ["최종 미팅"]  # next_action
    assert await action_case.search(keyword="예산") == ["첫 통화"]  # memo
    assert await action_case.search(keyword="특이") == ["레거시"]  # NULL next_action이어도 안전
    assert await action_case.search(keyword="%") == ["첫 통화"]
    assert await action_case.search(keyword="_") == []


async def test_search_filters_by_due_range_inclusive_and_excludes_null(action_case: Case) -> None:
    await _seed(action_case)
    await action_case.add_legacy(action="레거시")

    assert await action_case.search(due_from=date(2026, 2, 1), due_to=date(2026, 2, 10)) == [
        "최종 미팅",
        "킥오프 미팅",
        "첫 통화",
    ]
    assert await action_case.search(due_from=date(2026, 2, 10)) == ["최종 미팅", "첫 통화"]
    assert await action_case.search(due_to=date(2026, 2, 1)) == ["킥오프 미팅"]
    assert await action_case.search(due_from=date(2026, 2, 11)) == []


async def test_search_sorts_by_due_date_with_nulls_last(action_case: Case) -> None:
    await _seed(action_case)
    await action_case.add_legacy(action="레거시 A", acted_at=NOW + timedelta(days=9))
    await action_case.add_legacy(action="레거시 B", acted_at=NOW + timedelta(days=8))

    asc = await action_case.search(sort=DealActionSort.DUE_DATE_ASC)
    desc = await action_case.search(sort=DealActionSort.DUE_DATE_DESC)

    # 같은 계획일은 진행 일시 내림차순, NULL은 방향과 무관하게 마지막
    assert asc == ["킥오프 미팅", "최종 미팅", "첫 통화", "레거시 A", "레거시 B"]
    assert desc == ["최종 미팅", "첫 통화", "킥오프 미팅", "레거시 A", "레거시 B"]


async def test_search_by_deal_and_period_and_paging(action_case: Case) -> None:
    await _seed(action_case)
    other = make_deal_action(action="다른 딜", acted_at=NOW + timedelta(days=5))
    await action_case.add(other)

    assert await action_case.search(deal_id=other.details.deal_id) == ["다른 딜"]
    assert await action_case.search(
        acted_from=NOW + timedelta(days=1), acted_to=NOW + timedelta(days=5)
    ) == ["최종 미팅", "킥오프 미팅"]
    assert await action_case.search(offset=1, limit=2) == ["최종 미팅", "킥오프 미팅"]


async def test_search_rejects_invalid_criteria(action_case: Case) -> None:
    with pytest.raises(InvalidValueError):
        await action_case.search(limit=0)
