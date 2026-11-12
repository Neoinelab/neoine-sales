"""DealRepository의 Status 진입 시각: 저장·갱신·touch. Fake와 SQL 공통.

`get`/`get_item`/`search`가 돌려주는 Deal의 `status_entry`는 저장된 시각과 현재 status_key로 만들고,
`update`는 `status_changed_at`을 쓴다. 저장소 `touch`(연락처·첨부의 수정 시각)는 건드리지 않는다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.deal.status_entry import StatusEntry
from tests.factories import NOW, later, make_deal, make_sync

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def test_status_changed_at_round_trips_on_add(deal_case: DealCase) -> None:
    """Deal 저장 시 Status 진입 시각이 그대로 읽히는지 확인한다."""
    # given: 생성 시각이 있는 Deal이 있다
    deal = make_deal(later(10), code=CODE, status_key="introduction", forecast_key="best")
    # when: 저장하고 다시 읽는다
    await deal_case.add(deal)

    stored = await deal_case.deals.get(deal.id)

    # then: Status 진입 시각이 생성 시각이다
    assert stored.status_entry == StatusEntry(status_key="introduction", changed_at=later(10))
    assert stored.status_changed_at == later(10)


async def test_status_changed_at_round_trips_on_update(deal_case: DealCase) -> None:
    """Status를 바꿔 수정하면 진입 시각이 수정 시각으로 저장되는지 확인한다."""
    # given: 저장된 Deal의 Status를 바꾸고 수정 시각을 갱신해 둔다
    deal = make_deal(code=CODE, status_key="prospecting")
    await deal_case.add(deal)
    loaded = await deal_case.deals.get(deal.id)
    loaded.revise(
        details=loaded.details,
        sync=make_sync("introduction", "pipeline"),
        customer_id=loaded.customer_id,
        bant=loaded.bant,
    )
    loaded.touch(later(100))

    # when: Deal을 수정 저장한다
    await deal_case.deals.update(loaded)

    # then: 새 Status와 진입 시각, 수정 시각이 저장된다
    stored = await deal_case.deals.get(deal.id)
    assert stored.status_entry == StatusEntry(status_key="introduction", changed_at=later(100))
    assert stored.updated_at == later(100)


async def test_update_without_a_status_change_keeps_status_changed_at(deal_case: DealCase) -> None:
    """Status 변경 없는 수정은 진입 시각을 유지하는지 확인한다."""
    # given: 저장된 Deal을 같은 Status로 수정해 둔다
    deal = make_deal(code=CODE)
    await deal_case.add(deal)
    loaded = await deal_case.deals.get(deal.id)
    loaded.revise(
        details=loaded.details,
        sync=make_sync("prospecting", "best"),
        customer_id=loaded.customer_id,
        bant=loaded.bant,
    )
    loaded.touch(later(100))

    # when: Deal을 수정 저장한다
    await deal_case.deals.update(loaded)

    # then: 진입 시각은 그대로고 수정 시각만 바뀐다
    stored = await deal_case.deals.get(deal.id)
    assert stored.status_changed_at == NOW
    assert stored.updated_at == later(100)


async def test_repository_touch_keeps_status_changed_at(deal_case: DealCase) -> None:
    """저장소 touch가 진입 시각을 건드리지 않는지 확인한다."""
    # given: Deal이 저장되어 있다
    deal = make_deal(code=CODE)
    await deal_case.add(deal)

    # when: touch로 수정 시각을 갱신한다
    await deal_case.deals.touch([deal.id], later(90))

    # then: 수정 시각만 바뀌고 진입 시각은 그대로다
    stored = await deal_case.deals.get(deal.id)
    assert stored.updated_at == later(90)
    assert stored.status_changed_at == NOW


async def test_get_item_and_search_carry_status_changed_at(deal_case: DealCase) -> None:
    """get_item과 search가 진입 시각을 함께 돌려주는지 확인한다."""
    # given: Status 진입 시각이 있는 Deal이 저장되어 있다
    deal = make_deal(later(30), code=CODE, status_key="introduction", forecast_key="best")
    await deal_case.add(deal)

    # when: get_item과 search로 조회한다
    item = await deal_case.deals.get_item(deal.id)
    found = await deal_case.deals.search(DealQuery())

    # then: 두 결과의 진입 시각이 저장된 시각이다
    assert item.deal.status_changed_at == later(30)
    assert [i.deal.status_changed_at for i in found] == [later(30)]
