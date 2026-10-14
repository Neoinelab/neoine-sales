"""DealRepository.summarize_pipeline 계약과 stage 저장·필터 계약(Fake와 SQL 공통)."""

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from app.application.ports.deal_repository import DealQuery
from app.domain.common.money import Money
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.stage import DealStage
from tests.factories import later, make_deal, make_stage_changer
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.deal.entities import Deal
    from tests.contracts.conftest import RepositoryCase


def _deal(
    number: int, stage: DealStage, amount: str, currency: str = "KRW", **details: object
) -> Deal:
    deal = make_deal(
        later(number), code=f"P-{number}", revenue=Money(Decimal(amount), currency), **details
    )
    if stage is not DealStage.PROSPECTING:
        deal.change_stage(stage, reason="사유", changed_by=make_stage_changer(), now=later(number))
    return deal


async def _summary(case: RepositoryCase) -> dict[tuple[DealStage, str], tuple[int, Decimal]]:
    totals = await case.repository.summarize_pipeline()
    result = {(t.stage, t.currency): (t.deal_count, t.amount) for t in totals}
    assert len(result) == len(list(totals)), "같은 (단계, 통화)가 두 줄로 나오면 안 된다"
    return result


async def test_summarize_of_an_empty_repository_is_empty(deal_case: RepositoryCase) -> None:
    assert list(await deal_case.repository.summarize_pipeline()) == []


async def test_summarize_excludes_removed_and_groups_by_stage_and_currency(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(_deal(1, DealStage.PROSPECTING, "100"))
    await deal_case.add(_deal(2, DealStage.PROSPECTING, "50"))
    await deal_case.add(_deal(3, DealStage.PROSPECTING, "7", "USD"))
    await deal_case.add(_deal(4, DealStage.LOST, "30"))
    gone = _deal(5, DealStage.LOST, "1000")
    await deal_case.add(gone)
    await deal_case.repository.delete(gone.id)

    summary = await _summary(deal_case)

    assert summary == {
        (DealStage.PROSPECTING, "KRW"): (2, Decimal(150)),
        (DealStage.PROSPECTING, "USD"): (1, Decimal(7)),
        (DealStage.LOST, "KRW"): (1, Decimal(30)),
    }


async def test_summarize_keeps_four_decimal_places(deal_case: RepositoryCase) -> None:
    await deal_case.add(_deal(1, DealStage.INTRODUCTION, "0.0001"))
    await deal_case.add(_deal(2, DealStage.INTRODUCTION, "0.0002"))

    summary = await _summary(deal_case)

    assert summary[(DealStage.INTRODUCTION, "KRW")] == (2, Decimal("0.0003"))


async def test_summarize_does_not_overflow_the_money_limit(deal_case: RepositoryCase) -> None:
    big = "9999999999999999.9999"
    await deal_case.add(_deal(1, DealStage.LOST, big))
    await deal_case.add(_deal(2, DealStage.LOST, big))

    summary = await _summary(deal_case)

    assert summary[(DealStage.LOST, "KRW")] == (2, Decimal(big) * 2)


async def test_update_persists_stage(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="S-1")
    await deal_case.add(deal)
    deal.change_stage(
        DealStage.POC_COMPLETED, reason=None, changed_by=make_stage_changer(), now=later(10)
    )

    await deal_case.repository.update(deal)

    stored = await deal_case.repository.get(deal.id)
    assert stored.stage is DealStage.POC_COMPLETED
    assert stored.updated_at == later(10)


async def test_new_deal_is_stored_at_prospecting(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="S-1")
    await deal_case.add(deal)

    assert (await deal_case.repository.get(deal.id)).stage is DealStage.PROSPECTING


async def test_updating_details_keeps_the_stored_stage(deal_case: RepositoryCase) -> None:
    deal = _deal(1, DealStage.PRICE_NEGOTIATION, "10")
    await deal_case.add(deal)
    loaded = await deal_case.repository.get(deal.id)
    deal_case.change(loaded, later(30))

    await deal_case.repository.update(loaded)

    assert (await deal_case.repository.get(deal.id)).stage is DealStage.PRICE_NEGOTIATION


async def test_get_for_update_returns_the_same_deal(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="S-1")
    await deal_case.add(deal)

    locked = await deal_case.repository.get(deal.id, for_update=True)

    assert locked == deal
    assert locked.stage is DealStage.PROSPECTING


async def test_get_for_update_of_a_removed_deal_raises_not_found(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="S-1")
    await deal_case.add(deal)
    await deal_case.repository.delete(deal.id)

    with pytest.raises(DealNotFoundError):
        await deal_case.repository.get(deal.id, for_update=True)


async def test_search_filters_by_stage(deal_case: RepositoryCase) -> None:
    await deal_case.add(_deal(1, DealStage.PROSPECTING, "1"))
    await deal_case.add(_deal(2, DealStage.LOST, "1"))
    await deal_case.add(_deal(3, DealStage.LOST, "1"))
    await deal_case.add(_deal(4, DealStage.CONTRACT_COMPLETED, "1"))

    found = await deal_case.repository.search(DealQuery(stage=DealStage.LOST))

    assert [d.details.code.value for d in found] == ["P-2", "P-3"]
    assert all(d.stage is DealStage.LOST for d in found)


async def test_search_stage_combines_with_other_conditions(deal_case: RepositoryCase) -> None:
    await deal_case.add(_deal(1, DealStage.LOST, "1", owner_user_id=uid("kim")))
    await deal_case.add(_deal(2, DealStage.LOST, "1", owner_user_id=uid("park")))
    await deal_case.add(_deal(3, DealStage.PROSPECTING, "1", owner_user_id=uid("park")))

    found = await deal_case.repository.search(
        DealQuery(stage=DealStage.LOST, owner_user_id=uid("park"))
    )

    assert [d.details.code.value for d in found] == ["P-2"]


async def test_search_stage_excludes_removed_deals(deal_case: RepositoryCase) -> None:
    gone = _deal(1, DealStage.LOST, "1")
    await deal_case.add(gone)
    await deal_case.repository.delete(gone.id)

    assert await deal_case.repository.search(DealQuery(stage=DealStage.LOST)) == []


async def test_search_stage_pages_within_the_stage(deal_case: RepositoryCase) -> None:
    for number in range(1, 5):
        await deal_case.add(_deal(number, DealStage.LOST, "1"))

    found = await deal_case.repository.search(DealQuery(stage=DealStage.LOST, offset=1, limit=2))

    assert [d.details.code.value for d in found] == ["P-2", "P-3"]
