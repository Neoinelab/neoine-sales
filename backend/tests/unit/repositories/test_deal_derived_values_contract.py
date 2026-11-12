"""DealRepository의 파생값 계약: next_action과 last_updated_at.

Fake와 SQL(PostgreSQL)에 같은 기대값. 가장 최근에 수행한(acted_at) Action의 다음 진행 계획이
next_action이고, last_updated_at은 모든 Action 중 가장 최근 수행 시각이다(Action이 없으면 Deal
등록 시각이고 Deal 수정 시각은 반영하지 않는다).
`search`와 `get_item`이 같은 값을 준다.
"""

from datetime import date
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery, NextActionSummary
from app.domain.deal_action.next_action_status import NextActionStatus
from tests.factories import later, make_deal

if TYPE_CHECKING:
    from app.application.ports.deal_repository import DealListItem
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def _item(case: DealCase, code: str = CODE) -> DealListItem:
    item: DealListItem = await case.deals.get_item(make_deal(code=code).id)
    return item


async def test_a_deal_without_actions_has_no_next_action_and_its_registration_time(
    deal_case: DealCase,
) -> None:
    """Action이 없는 Deal은 Next Action이 없고 최종 업데이트가 등록 시각이다."""
    # given: Action 없이 등록 후 수정(touch)만 된 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.touch([deal.id], later(50))  # Deal 수정은 최종 업데이트가 아니다

    # when: 목록 항목을 조회한다 (전제: Fake·SQL 공통)
    item = await _item(deal_case)

    # then: Next Action은 없고 최종 업데이트는 등록 시각이다
    assert item.next_action is None
    assert item.last_updated_at == later(5)


async def test_the_most_recent_action_provides_both_values(deal_case: DealCase) -> None:
    """가장 최근 Action이 Next Action과 최종 업데이트를 정한다."""
    # given: Next Action이 있는 Action 하나를 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(
        deal, acted_at=later(100), next_action="계약서 검토", due_date=date(2026, 2, 5)
    )

    # when: 목록 항목을 조회한다 (전제: Fake·SQL 공통)
    item = await _item(deal_case)

    # then: 그 Action의 Next Action과 수행 시각이다
    assert item.next_action == NextActionSummary(
        text="계약서 검토", due_date=date(2026, 2, 5), status=NextActionStatus.OPEN
    )
    assert item.last_updated_at == later(100)


async def test_the_action_with_the_latest_acted_at_wins_not_the_last_saved(
    deal_case: DealCase,
) -> None:
    """마지막에 저장한 Action이 아니라 수행 시각이 가장 늦은 Action이 이긴다."""
    # given: 수행 시각이 늦은 Action을 먼저, 이른 Action을 나중에 저장한 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(200), next_action="나중 일")
    await deal_case.add_action(deal, acted_at=later(100), next_action="먼저 한 일")

    # when: 목록 항목을 조회한다 (전제: Fake·SQL 공통)
    item = await _item(deal_case)

    # then: 수행 시각이 늦은 Action의 값이다
    assert item.next_action is not None
    assert item.next_action.text == "나중 일"
    assert item.last_updated_at == later(200)


async def test_an_action_older_than_the_deal_update_still_sets_the_last_update(
    deal_case: DealCase,
) -> None:
    """Deal 수정보다 오래된 Action이라도 최종 업데이트를 정한다."""
    # given: Action보다 나중에 수정(touch)된 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.deals.touch([deal.id], later(500))
    await deal_case.add_action(deal, acted_at=later(10), next_action="오래된 일")

    # when: 목록 항목을 조회한다 (전제: Fake·SQL 공통)
    item = await _item(deal_case)

    # then: 최종 업데이트는 Action 수행 시각이다
    assert item.last_updated_at == later(10)
    assert item.next_action is not None
    assert item.next_action.text == "오래된 일"


async def test_actions_of_other_deals_do_not_leak(deal_case: DealCase) -> None:
    """다른 Deal의 Action은 섞이지 않는다."""
    # given: 한 Deal에만 Action이 있는 Deal 두 개
    first, second = make_deal(later(5), code=CODE), make_deal(later(5), code="20261016-A002")
    await deal_case.add(first)
    await deal_case.add(second)
    await deal_case.add_action(first, acted_at=later(100), next_action="첫 번째 일")

    # when: Action이 없는 Deal의 항목을 조회한다 (전제: Fake·SQL 공통)
    other = await _item(deal_case, "20261016-A002")

    # then: Next Action이 없고 최종 업데이트는 등록 시각이다
    assert other.next_action is None
    assert other.last_updated_at == later(5)


async def test_search_gives_the_same_derived_values_per_row(deal_case: DealCase) -> None:
    """목록 검색도 행마다 같은 파생값을 준다."""
    # given: Action이 없는 Deal과 Action이 있는 Deal
    quiet = make_deal(later(5), code=CODE)
    busy = make_deal(later(6), code="20261016-A002")
    await deal_case.add(quiet)
    await deal_case.add(busy)
    await deal_case.add_action(busy, acted_at=later(100), next_action="후속 미팅")

    # when: Deal 목록을 검색한다 (전제: Fake·SQL 공통)
    rows = {i.deal.id.value: i for i in await deal_case.deals.search(DealQuery())}

    # then: 행마다 Next Action과 최종 업데이트가 각 Deal 기준이다
    assert rows[CODE].next_action is None
    assert rows[CODE].last_updated_at == later(5)
    busy_summary = rows["20261016-A002"].next_action
    assert busy_summary is not None
    assert busy_summary.text == "후속 미팅"
    assert rows["20261016-A002"].last_updated_at == later(100)


async def test_deleting_the_latest_action_falls_back_to_the_previous_one(
    deal_case: DealCase,
) -> None:
    """가장 최근 Action을 삭제하면 이전 Action 값으로 돌아간다."""
    # given: 이전 Action과 최근 Action을 가진 Deal
    deal = make_deal(later(5), code=CODE)
    await deal_case.add(deal)
    await deal_case.add_action(deal, acted_at=later(100), next_action="이전 일")
    latest = await deal_case.add_action(deal, acted_at=later(200), next_action="최근 일")

    # when: 최근 Action을 삭제하고 항목을 다시 조회한다 (전제: Fake·SQL 공통)
    await deal_case.actions.delete(latest.id)

    # then: 이전 Action의 Next Action과 수행 시각이다
    item = await _item(deal_case)
    assert item.next_action is not None
    assert item.next_action.text == "이전 일"
    assert item.last_updated_at == later(100)
