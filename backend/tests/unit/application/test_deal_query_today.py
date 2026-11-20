"""DealQuery의 업무 날짜(today): Next Action 기준 행(RK-R1)을 고를 때 쓰는 "오늘"."""

from datetime import date

from app.application.ports.deal_action_repository import NextActionStatusFilter
from app.application.ports.deal_repository import DealQuery

TODAY = date(2026, 1, 10)


def test_today_defaults_to_none() -> None:
    """오늘은 기본이 없다(저장소가 채우라고 요구한다)."""
    # when: 조건 없이 DealQuery를 만든다
    query = DealQuery()

    # then: today가 None이다
    assert query.today is None


def test_with_today_returns_a_copy_that_keeps_every_other_condition() -> None:
    """with_today는 today만 채운 사본을 돌려주고 원본·다른 조건은 그대로다."""
    # given: 여러 조건을 가진 질의
    query = DealQuery(
        keyword="erp",
        overdue=True,
        next_action_status=NextActionStatusFilter.OPEN,
        offset=20,
        limit=10,
    )

    # when: 오늘을 채운다
    filled = query.with_today(TODAY)

    # then: 사본에만 today가 있고 나머지 조건은 같다
    assert filled.today == TODAY
    assert query.today is None
    assert filled.keyword == "erp"
    assert filled.overdue is True
    assert filled.next_action_status is NextActionStatusFilter.OPEN
    assert (filled.offset, filled.limit) == (20, 10)


def test_with_today_overwrites_an_earlier_today() -> None:
    """이미 today가 있으면 새 값으로 바뀐 사본을 돌려준다."""
    # when: 두 번 채운다
    filled = DealQuery().with_today(TODAY).with_today(date(2026, 2, 1))

    # then: 마지막 값이다
    assert filled.today == date(2026, 2, 1)
