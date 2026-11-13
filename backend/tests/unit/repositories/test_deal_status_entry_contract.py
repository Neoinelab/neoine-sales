"""DealRepository의 Status 진입일: 저장·갱신·touch. Fake와 SQL 공통.

`get`/`get_item`/`search`가 돌려주는 Deal의 `status_entry`는 저장된 진입일(date)과 현재 status_key로
만들고, `update`는 `status_changed_on`을 쓴다. 저장소 `touch`(연락처·첨부의 수정 시각)는
건드리지 않는다.
"""

from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.deal.status_entry import StatusEntry
from tests.factories import date_after, later, make_deal, make_sync

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def test_status_changed_on_round_trips_on_add(deal_case: DealCase) -> None:
    """Deal 저장 시 Status 진입일이 그대로 읽히는지 확인한다."""
    # given: 생성 시각이 있는 Deal이 있다
    deal = make_deal(later(10), code=CODE, status_key="introduction", forecast_key="best")
    # when: 저장하고 다시 읽는다
    await deal_case.add(deal)

    stored = await deal_case.deals.get(deal.id)

    # then: Status 진입일이 생성 시각의 업무 날짜다
    assert stored.status_entry == StatusEntry(status_key="introduction", changed_on=date_after(0))
    assert stored.status_changed_on == date_after(0)


async def test_status_changed_on_round_trips_on_update(deal_case: DealCase) -> None:
    """Status를 바꿔 수정하면 진입일이 수정 시각의 업무 날짜로 저장되는지 확인한다."""
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
    loaded.touch(later(2 * 86400))  # 이틀 뒤

    # when: Deal을 수정 저장한다
    await deal_case.deals.update(loaded)

    # then: 새 Status와 진입일(이틀 뒤 날짜), 수정 시각이 저장된다
    stored = await deal_case.deals.get(deal.id)
    assert stored.status_entry == StatusEntry(status_key="introduction", changed_on=date_after(2))
    assert stored.updated_at == later(2 * 86400)


async def test_update_without_a_status_change_keeps_status_changed_on(deal_case: DealCase) -> None:
    """Status 변경 없는 수정은 진입일을 유지하는지 확인한다."""
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
    loaded.touch(later(2 * 86400))

    # when: Deal을 수정 저장한다
    await deal_case.deals.update(loaded)

    # then: 진입일은 그대로고 수정 시각만 바뀐다
    stored = await deal_case.deals.get(deal.id)
    assert stored.status_changed_on == date_after(0)
    assert stored.updated_at == later(2 * 86400)


async def test_repository_touch_keeps_status_changed_on(deal_case: DealCase) -> None:
    """저장소 touch가 진입일을 건드리지 않는지 확인한다."""
    # given: Deal이 저장되어 있다
    deal = make_deal(code=CODE)
    await deal_case.add(deal)

    # when: touch로 수정 시각을 갱신한다
    await deal_case.deals.touch([deal.id], later(2 * 86400))

    # then: 수정 시각만 바뀌고 진입일은 그대로다
    stored = await deal_case.deals.get(deal.id)
    assert stored.updated_at == later(2 * 86400)
    assert stored.status_changed_on == date_after(0)


async def test_get_item_and_search_carry_status_changed_on(deal_case: DealCase) -> None:
    """get_item과 search가 진입일을 함께 돌려주는지 확인한다."""
    # given: Status 진입일이 있는 Deal이 저장되어 있다
    deal = make_deal(later(30), code=CODE, status_key="introduction", forecast_key="best")
    await deal_case.add(deal)

    # when: get_item과 search로 조회한다
    item = await deal_case.deals.get_item(deal.id)
    found = await deal_case.deals.search(DealQuery())

    # then: 두 결과의 진입일이 저장된 날짜다
    assert item.deal.status_changed_on == date_after(0)
    assert [i.deal.status_changed_on for i in found] == [date_after(0)]
