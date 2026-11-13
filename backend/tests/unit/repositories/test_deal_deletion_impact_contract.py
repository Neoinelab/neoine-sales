"""DealRepository.deletion_impact 계약(R3): 지우면 함께 사라지는 이력·활동 건수.

Fake와 SQL(PostgreSQL)에 같은 기대값. 첨부 파일은 P2b 전이라 attachment_count는 항상 0이다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from tests.factories import date_after, later, make_deal
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"
OTHER = "20261016-A002"


def _entry(code: str, at: int) -> DealHistoryEntry:
    draft = HistoryDraft(HistoryCategory.OTHER, "Deal Name", "A", "B")
    return DealHistoryEntry(None, make_deal(code=code).id, later(at), OWNER_ID, draft)


async def test_a_deal_without_history_or_actions_has_zero_counts(deal_case: DealCase) -> None:
    """이력·Action이 없는 Deal의 건수는 모두 0이다.

    테스트 코드: DD-047
    """
    # given: 이력·Action이 없는 Deal
    await deal_case.add(make_deal(code=CODE))

    # when: 삭제 영향을 읽는다
    impact = await deal_case.deals.deletion_impact(make_deal(code=CODE).id)

    # then: 네 건수가 0이다
    assert impact == DealDeletionImpact(
        history_count=0, action_count=0, attachment_count=0, license_contract_count=0
    )


async def test_history_and_actions_are_counted_per_kind(deal_case: DealCase) -> None:
    """이력과 Action을 종류별로 센다.

    테스트 코드: DD-047
    """
    # given: 이력 3건과 Action 2건이 있는 Deal
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(CODE, 2), _entry(CODE, 3)])
    await deal_case.add_action(deal, acted_on=date_after(1))
    await deal_case.add_action(deal, acted_on=date_after(2))

    # when: 삭제 영향을 읽는다
    impact = await deal_case.deals.deletion_impact(deal.id)

    # then: 이력 3, Action 2다
    assert impact == DealDeletionImpact(
        history_count=3, action_count=2, attachment_count=0, license_contract_count=0
    )


async def test_other_deals_are_not_counted(deal_case: DealCase) -> None:
    """다른 Deal의 이력·Action은 세지 않는다.

    테스트 코드: DD-048
    """
    # given: 첫 Deal 이력 1건, 둘째 Deal 이력 2건·Action 1건
    first, second = make_deal(code=CODE), make_deal(code=OTHER)
    await deal_case.add(first)
    await deal_case.add(second)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(OTHER, 2), _entry(OTHER, 3)])
    await deal_case.add_action(second, acted_on=date_after(1))

    # when: 첫 Deal의 삭제 영향을 읽는다
    impact = await deal_case.deals.deletion_impact(first.id)

    # then: 이력 1, Action 0이다
    assert impact == DealDeletionImpact(
        history_count=1, action_count=0, attachment_count=0, license_contract_count=0
    )


async def test_the_counts_are_what_a_delete_would_remove(deal_case: DealCase) -> None:
    """센 건수는 삭제로 실제 지워지는 건수와 같다.

    테스트 코드: DD-047
    """
    # given: 이력 2건과 Action 1건이 있는 Deal의 삭제 영향
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    await deal_case.history.add_many([_entry(CODE, 1), _entry(CODE, 2)])
    await deal_case.add_action(deal, acted_on=date_after(1))
    impact = await deal_case.deals.deletion_impact(deal.id)

    # when: Deal을 삭제한다
    await deal_case.deals.delete(deal.id)

    # then: 이력·Action이 모두 사라졌고 센 값은 (2, 1)이었다
    assert list(await deal_case.history.list(deal.id)) == []
    assert await deal_case.actions_of(deal.id) == []
    assert (impact.history_count, impact.action_count) == (2, 1)


async def test_an_unknown_deal_is_not_found(deal_case: DealCase) -> None:
    """없는 Deal의 삭제 영향은 찾을 수 없음 오류다.

    테스트 코드: DD-049
    """
    # when·then: 없는 Deal의 삭제 영향을 읽는다 → Deal 없음 오류다
    with pytest.raises(DealNotFoundError):
        await deal_case.deals.deletion_impact(make_deal(code=CODE).id)
