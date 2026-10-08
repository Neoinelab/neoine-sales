"""Deal.owner_user_id 계약(Fake와 SQL 공통): 저장·왕복, 정확 일치 검색, AND, 파이프라인 집계."""

from decimal import Decimal
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.common.money import Money
from app.domain.deal.stage import DealStage
from tests.factories import later, make_deal, make_stage_changer

if TYPE_CHECKING:
    from tests.contracts.conftest import RepositoryCase


async def _codes(case: RepositoryCase, **criteria: object) -> list[str]:
    found = await case.repository.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return [d.details.code.value for d in found]


async def test_owner_user_id_round_trips(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id="u-1")
    await deal_case.add(deal)

    assert (await deal_case.repository.get(deal.id)).owner_user_id == "u-1"
    assert (await deal_case.repository.get_by_code(deal.details.code)).owner_user_id == "u-1"
    assert [d.owner_user_id for d in await deal_case.repository.list()] == ["u-1"]


async def test_missing_owner_user_id_round_trips_as_none(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1")
    await deal_case.add(deal)

    assert (await deal_case.repository.get(deal.id)).owner_user_id is None


async def test_owner_user_id_keeps_non_ascii_and_case(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id="김영업@Corp.Example")
    await deal_case.add(deal)

    assert (await deal_case.repository.get(deal.id)).owner_user_id == "김영업@Corp.Example"


async def test_update_keeps_the_stored_owner_user_id(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id="u-1")
    await deal_case.add(deal)
    loaded = await deal_case.repository.get(deal.id)
    deal_case.change(loaded, later(30))

    await deal_case.repository.update(loaded)

    stored = await deal_case.repository.get(deal.id)
    assert stored.owner_user_id == "u-1"
    assert stored.details.name == "변경된 딜"


async def test_search_filters_by_owner_user_id_exactly(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id="alice"))
    await deal_case.add(make_deal(later(2), code="B-1", owner_user_id="bob"))
    await deal_case.add(make_deal(later(3), code="A-2", owner_user_id="alice"))

    assert await _codes(deal_case, owner_user_id="alice") == ["A-1", "A-2"]
    assert await _codes(deal_case, owner_user_id="bob") == ["B-1"]


async def test_search_owner_user_id_is_case_sensitive_and_not_a_prefix_match(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id="Alice"))
    await deal_case.add(make_deal(later(2), code="A-2", owner_user_id="alice2"))

    assert await _codes(deal_case, owner_user_id="alice") == []
    assert await _codes(deal_case, owner_user_id="ALICE") == []
    assert await _codes(deal_case, owner_user_id="Alice") == ["A-1"]


async def test_search_owner_user_id_does_not_treat_like_wildcards_specially(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id="u_1"))
    await deal_case.add(make_deal(later(2), code="A-2", owner_user_id="uX1"))

    assert await _codes(deal_case, owner_user_id="u_1") == ["A-1"]
    assert await _codes(deal_case, owner_user_id="%") == []


async def test_search_without_owner_user_id_returns_everyones_deals(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id="alice"))
    await deal_case.add(make_deal(later(2), code="N-1"))

    assert await _codes(deal_case) == ["A-1", "N-1"]


async def test_deals_without_owner_user_are_never_mine(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="OLD-1"))
    await deal_case.add(make_deal(later(2), code="A-1", owner_user_id="alice"))

    assert await _codes(deal_case, owner_user_id="alice") == ["A-1"]
    assert await _codes(deal_case, owner_user_id="anyone") == []


async def test_search_owner_user_id_combines_with_stage_and_keyword(
    deal_case: RepositoryCase,
) -> None:
    lost = make_deal(later(1), code="ERP-1", owner_user_id="alice")
    lost.change_stage(DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(1))
    await deal_case.add(lost)
    await deal_case.add(make_deal(later(2), code="ERP-2", owner_user_id="alice"))
    other_lost = make_deal(later(3), code="ERP-3", owner_user_id="bob")
    other_lost.change_stage(
        DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(3)
    )
    await deal_case.add(other_lost)
    await deal_case.add(make_deal(later(4), code="CRM-1", owner_user_id="alice", name="CRM"))

    assert await _codes(deal_case, owner_user_id="alice", stage=DealStage.LOST) == ["ERP-1"]
    assert await _codes(deal_case, owner_user_id="alice", keyword="erp") == ["ERP-1", "ERP-2"]
    assert await _codes(deal_case, owner_user_id="alice", stage=DealStage.LOST, keyword="crm") == []


async def test_search_owner_user_id_excludes_deleted_deals_and_pages_within_mine(
    deal_case: RepositoryCase,
) -> None:
    for number in range(1, 5):
        await deal_case.add(make_deal(later(number), code=f"A-{number}", owner_user_id="alice"))
    await deal_case.add(make_deal(later(5), code="B-1", owner_user_id="bob"))
    gone = await deal_case.repository.get((await deal_case.repository.search(DealQuery()))[0].id)
    gone.soft_delete(later(20))
    await deal_case.repository.update(gone)

    assert await _codes(deal_case, owner_user_id="alice") == ["A-2", "A-3", "A-4"]
    assert await _codes(deal_case, owner_user_id="alice", offset=1, limit=1) == ["A-3"]


async def test_soft_deleted_deal_keeps_its_owner_user_id(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id="u-1")
    await deal_case.add(deal)
    deal.soft_delete(later(10))
    await deal_case.repository.update(deal)

    stored = await deal_case.repository.get(deal.id, include_deleted=True)

    assert stored.owner_user_id == "u-1"


async def test_summarize_for_one_owner_user(deal_case: RepositoryCase) -> None:
    mine_moved = make_deal(
        later(1), code="A-1", owner_user_id="alice", revenue=Money(Decimal("10"))
    )
    mine_moved.change_stage(
        DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(1)
    )
    await deal_case.add(mine_moved)
    await deal_case.add(
        make_deal(later(2), code="A-2", owner_user_id="alice", revenue=Money(Decimal("5")))
    )
    await deal_case.add(
        make_deal(later(3), code="B-1", owner_user_id="bob", revenue=Money(Decimal("1000")))
    )
    await deal_case.add(make_deal(later(4), code="N-1", revenue=Money(Decimal("2000"))))
    gone = make_deal(later(5), code="A-3", owner_user_id="alice", revenue=Money(Decimal("7")))
    await deal_case.add(gone)
    gone.soft_delete(later(20))
    await deal_case.repository.update(gone)

    totals = await deal_case.repository.summarize_pipeline(owner_user_id="alice")

    assert {(t.stage, t.currency): (t.deal_count, t.amount) for t in totals} == {
        (DealStage.PROSPECTING, "KRW"): (1, Decimal(5)),
        (DealStage.LOST, "KRW"): (1, Decimal(10)),
    }


async def test_summarize_without_owner_user_id_counts_everyone(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id="alice"))
    await deal_case.add(make_deal(later(2), code="N-1"))

    totals = await deal_case.repository.summarize_pipeline()

    assert sum(t.deal_count for t in totals) == 2


async def test_summarize_for_an_owner_user_without_deals_is_empty(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="OLD-1"))

    assert list(await deal_case.repository.summarize_pipeline(owner_user_id="alice")) == []


async def test_deal_details_do_not_decide_ownership(deal_case: RepositoryCase) -> None:
    """자유 텍스트 Deal Owner(details.owner)가 같아도 owner_user_id가 다르면 내 딜이 아니다."""
    await deal_case.add(make_deal(later(1), code="A-1", owner="박영업", owner_user_id="alice"))
    await deal_case.add(make_deal(later(2), code="B-1", owner="박영업", owner_user_id="bob"))

    assert await _codes(deal_case, owner_user_id="alice") == ["A-1"]
