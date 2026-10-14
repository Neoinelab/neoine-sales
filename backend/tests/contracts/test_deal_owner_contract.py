"""Deal 담당자(details.owner_user_id)·등록자(registered_by_user_id) 계약(Fake와 SQL 공통).

저장·왕복, 담당자 user id 정확 일치 검색, AND 결합, 퇴사한 담당자, 키워드(담당자 이름), 집계.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.common.money import Money
from app.domain.deal.stage import DealStage
from tests.factories import later, make_deal, make_deal_details, make_stage_changer
from tests.support.user_ids import OWNER_ID, uid
from tests.support.user_seed import ensure_users

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId
    from tests.contracts.conftest import RepositoryCase


async def _codes(case: RepositoryCase, **criteria: object) -> list[str]:
    found = await case.repository.search(DealQuery(**criteria))  # type: ignore[arg-type]
    return [d.details.code.value for d in found]


async def _resign(case: RepositoryCase, user_id: UserId) -> None:
    assert case.users is not None
    user = await case.users.get(user_id)
    user.resign(later(100))
    await case.users.update(user)


async def test_owner_and_registrant_round_trip(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id=uid("alice"), registered_by_user_id=uid("bob"))
    await deal_case.add(deal)

    for stored in (
        await deal_case.repository.get(deal.id),
        await deal_case.repository.get_by_code(deal.details.code),
        (await deal_case.repository.list())[0],
    ):
        assert stored.details.owner_user_id == uid("alice")
        assert stored.registered_by_user_id == uid("bob")


async def test_missing_registrant_round_trips_as_none(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1")
    await deal_case.add(deal)

    stored = await deal_case.repository.get(deal.id)

    assert stored.registered_by_user_id is None
    assert stored.details.owner_user_id == OWNER_ID


async def test_update_keeps_the_registrant(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", registered_by_user_id=uid("bob"))
    await deal_case.add(deal)
    loaded = await deal_case.repository.get(deal.id)
    deal_case.change(loaded, later(30))

    await deal_case.repository.update(loaded)

    stored = await deal_case.repository.get(deal.id)
    assert stored.registered_by_user_id == uid("bob")
    assert stored.details.name == "변경된 딜"


async def test_update_persists_a_new_owner(deal_case: RepositoryCase) -> None:
    deal = make_deal(code="O-1", owner_user_id=uid("alice"))
    await deal_case.add(deal)
    assert deal_case.users is not None
    await ensure_users(deal_case.users, uid("carol"))
    loaded = await deal_case.repository.get(deal.id)
    loaded.update(
        make_deal_details(
            code=loaded.details.code,
            customer_id=loaded.details.customer_id,
            owner_user_id=uid("carol"),
        ),
        later(30),
    )

    await deal_case.repository.update(loaded)

    assert (await deal_case.repository.get(deal.id)).details.owner_user_id == uid("carol")


async def test_search_filters_by_owner_user_id_exactly(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id=uid("alice")))
    await deal_case.add(make_deal(later(2), code="B-1", owner_user_id=uid("bob")))
    await deal_case.add(make_deal(later(3), code="A-2", owner_user_id=uid("alice")))

    assert await _codes(deal_case, owner_user_id=uid("alice")) == ["A-1", "A-2"]
    assert await _codes(deal_case, owner_user_id=uid("bob")) == ["B-1"]
    assert await _codes(deal_case, owner_user_id=uid("nobody")) == []


async def test_search_without_owner_returns_everyones_deals(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id=uid("alice")))
    await deal_case.add(make_deal(later(2), code="B-1", owner_user_id=uid("bob")))

    assert await _codes(deal_case) == ["A-1", "B-1"]


async def test_registrant_does_not_decide_mine(deal_case: RepositoryCase) -> None:
    """내 딜=담당자 기준(결정 M): 등록자가 alice여도 담당자가 bob이면 alice의 딜이 아니다."""
    await deal_case.add(
        make_deal(
            later(1), code="A-1", owner_user_id=uid("alice"), registered_by_user_id=uid("bob")
        )
    )
    await deal_case.add(
        make_deal(
            later(2), code="B-1", owner_user_id=uid("bob"), registered_by_user_id=uid("alice")
        )
    )

    assert await _codes(deal_case, owner_user_id=uid("alice")) == ["A-1"]


async def test_search_owner_combines_with_stage_and_keyword(deal_case: RepositoryCase) -> None:
    alice, bob = uid("alice"), uid("bob")
    lost = make_deal(later(1), code="ERP-1", owner_user_id=alice)
    lost.change_stage(DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(1))
    await deal_case.add(lost)
    await deal_case.add(make_deal(later(2), code="ERP-2", owner_user_id=alice))
    other_lost = make_deal(later(3), code="ERP-3", owner_user_id=bob)
    other_lost.change_stage(
        DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(3)
    )
    await deal_case.add(other_lost)
    await deal_case.add(make_deal(later(4), code="CRM-1", owner_user_id=alice, name="CRM"))

    assert await _codes(deal_case, owner_user_id=alice, stage=DealStage.LOST) == ["ERP-1"]
    assert await _codes(deal_case, owner_user_id=alice, keyword="erp") == ["ERP-1", "ERP-2"]
    assert await _codes(deal_case, owner_user_id=alice, stage=DealStage.LOST, keyword="crm") == []


async def test_search_owner_excludes_removed_deals_and_pages_within_mine(
    deal_case: RepositoryCase,
) -> None:
    for number in range(1, 5):
        await deal_case.add(
            make_deal(later(number), code=f"A-{number}", owner_user_id=uid("alice"))
        )
    await deal_case.add(make_deal(later(5), code="B-1", owner_user_id=uid("bob")))
    first = (await deal_case.repository.search(DealQuery()))[0]
    await deal_case.repository.delete(first.id)

    assert await _codes(deal_case, owner_user_id=uid("alice")) == ["A-2", "A-3", "A-4"]
    assert await _codes(deal_case, owner_user_id=uid("alice"), offset=1, limit=1) == ["A-3"]


async def test_search_owner_user_id_finds_deals_of_a_resigned_owner(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="D-1", owner_user_id=uid("leaver")))
    await deal_case.add(make_deal(later(2), code="D-2"))
    await _resign(deal_case, uid("leaver"))

    assert await _codes(deal_case, owner_user_id=uid("leaver")) == ["D-1"]


async def test_keyword_matches_the_owners_login_id_when_there_is_no_display_name(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.add(make_deal(later(1), code="D-1", owner_user_id=uid("hong.gd")))
    await deal_case.add(make_deal(later(2), code="D-2", owner_user_id=uid("kim")))

    assert await _codes(deal_case, keyword="HONG") == ["D-1"]


async def test_keyword_matches_the_owners_display_name_even_after_resignation(
    deal_case: RepositoryCase,
) -> None:
    await deal_case.name_user(uid("leaver"), "이탈자")
    await deal_case.add(make_deal(later(1), code="D-1", owner_user_id=uid("leaver")))
    await deal_case.add(make_deal(later(2), code="D-2"))
    await _resign(deal_case, uid("leaver"))

    assert await _codes(deal_case, keyword="이탈자") == ["D-1"]


async def test_summarize_for_one_owner(deal_case: RepositoryCase) -> None:
    alice = uid("alice")
    mine_moved = make_deal(later(1), code="A-1", owner_user_id=alice, revenue=Money(Decimal("10")))
    mine_moved.change_stage(
        DealStage.LOST, reason="x", changed_by=make_stage_changer(), now=later(1)
    )
    await deal_case.add(mine_moved)
    await deal_case.add(
        make_deal(later(2), code="A-2", owner_user_id=alice, revenue=Money(Decimal("5")))
    )
    await deal_case.add(
        make_deal(later(3), code="B-1", owner_user_id=uid("bob"), revenue=Money(Decimal("1000")))
    )
    gone = make_deal(later(5), code="A-3", owner_user_id=alice, revenue=Money(Decimal("7")))
    await deal_case.add(gone)
    await deal_case.repository.delete(gone.id)

    totals = await deal_case.repository.summarize_pipeline(owner_user_id=alice)

    assert {(t.stage, t.currency): (t.deal_count, t.amount) for t in totals} == {
        (DealStage.PROSPECTING, "KRW"): (1, Decimal(5)),
        (DealStage.LOST, "KRW"): (1, Decimal(10)),
    }


async def test_summarize_without_owner_counts_everyone(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="A-1", owner_user_id=uid("alice")))
    await deal_case.add(make_deal(later(2), code="B-1", owner_user_id=uid("bob")))

    totals = await deal_case.repository.summarize_pipeline()

    assert sum(t.deal_count for t in totals) == 2


async def test_summarize_for_an_owner_without_deals_is_empty(deal_case: RepositoryCase) -> None:
    await deal_case.add(make_deal(later(1), code="B-1", owner_user_id=uid("bob")))

    assert list(await deal_case.repository.summarize_pipeline(owner_user_id=uid("alice"))) == []
