"""DealRepository의 Status 진입 시각(P3 AC-08·09): 저장·갱신·touch. Fake와 SQL 공통.

`get`/`get_item`/`search`가 돌려주는 Deal의 `status_entry`는 저장된 시각과 현재 status_key로 만들고,
`update`는 `status_changed_at`을 쓴다. 저장소 `touch`(연락처·첨부의 수정 시각)는 건드리지 않는다.
"""

from typing import TYPE_CHECKING

from app.domain.deal.status_entry import StatusEntry

from app.application.ports.deal_repository import DealQuery
from tests.factories import NOW, later, make_deal, make_sync

if TYPE_CHECKING:
    from tests.unit.repositories.deal_case import DealCase

CODE = "20261016-A001"


async def test_status_changed_at_round_trips_on_add(deal_case: DealCase) -> None:
    deal = make_deal(later(10), code=CODE, status_key="introduction", forecast_key="best")
    await deal_case.add(deal)

    stored = await deal_case.deals.get(deal.id)

    assert stored.status_entry == StatusEntry(status_key="introduction", changed_at=later(10))
    assert stored.status_changed_at == later(10)


async def test_status_changed_at_round_trips_on_update(deal_case: DealCase) -> None:
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

    await deal_case.deals.update(loaded)

    stored = await deal_case.deals.get(deal.id)
    assert stored.status_entry == StatusEntry(status_key="introduction", changed_at=later(100))
    assert stored.updated_at == later(100)


async def test_update_without_a_status_change_keeps_status_changed_at(deal_case: DealCase) -> None:
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

    await deal_case.deals.update(loaded)

    stored = await deal_case.deals.get(deal.id)
    assert stored.status_changed_at == NOW
    assert stored.updated_at == later(100)


async def test_repository_touch_keeps_status_changed_at(deal_case: DealCase) -> None:
    deal = make_deal(code=CODE)
    await deal_case.add(deal)

    await deal_case.deals.touch([deal.id], later(90))

    stored = await deal_case.deals.get(deal.id)
    assert stored.updated_at == later(90)
    assert stored.status_changed_at == NOW


async def test_get_item_and_search_carry_status_changed_at(deal_case: DealCase) -> None:
    deal = make_deal(later(30), code=CODE, status_key="introduction", forecast_key="best")
    await deal_case.add(deal)

    item = await deal_case.deals.get_item(deal.id)
    found = await deal_case.deals.search(DealQuery())

    assert item.deal.status_changed_at == later(30)
    assert [i.deal.status_changed_at for i in found] == [later(30)]
