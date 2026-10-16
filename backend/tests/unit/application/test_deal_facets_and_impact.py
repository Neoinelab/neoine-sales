"""ListDealFacets(AC-24)와 GetDealDeletionImpact(AC-26): 필터용 목록과 삭제 영향 건수."""

from typing import TYPE_CHECKING

import pytest

from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.deal.errors import DealNotFoundError
from tests.factories import make_register_input
from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_facets_are_the_distinct_non_blank_values_sorted_ignoring_case(env: DealEnv) -> None:
    await env.new_deal(vendor="sap", solution="Zeta")
    await env.new_deal(vendor="Oracle", solution="alpha")
    await env.new_deal(vendor="sap", solution="Beta")
    await env.new_deal(vendor="", solution="")

    facets = await env.facets.execute()

    assert list(facets.vendors) == ["Oracle", "sap"]
    assert list(facets.solutions) == ["alpha", "Beta", "Zeta"]


async def test_facets_of_an_empty_system_are_empty(env: DealEnv) -> None:
    facets = await env.facets.execute()

    assert (list(facets.vendors), list(facets.solutions)) == ([], [])


async def test_facets_follow_edits_and_deletions(env: DealEnv) -> None:
    kept = await env.new_deal(vendor="SAP")
    gone = await env.new_deal(vendor="Oracle")
    await env.update.execute(kept.item.deal.id.value, make_patch(vendor="Microsoft"), SALES)
    await env.delete.execute(gone.item.deal.id.value, gone.item.deal.id.value, SALES)

    facets = await env.facets.execute()

    assert list(facets.vendors) == ["Microsoft"]


async def test_the_impact_counts_the_history_and_actions_that_would_be_deleted(
    env: DealEnv,
) -> None:
    view = await env.new_deal()
    await env.update.execute(view.item.deal.id.value, make_patch(name="변경"), SALES)
    register = RegisterDealAction(env.uow_factory, env.clock)
    for _ in range(3):
        env.clock.advance(60)
        await register.execute(view.item.deal.id.value, make_register_input(), SALES)

    impact = await env.impact.execute(view.item.deal.id.value)

    # 이력 = 등록 1 + 수정 1 + Action 등록마다 category=action 1건 x 3 (AC-03)
    assert impact == DealDeletionImpact(history_count=1 + 1 + 3, action_count=3, attachment_count=0)


async def test_a_new_deal_has_only_its_registration_entry(env: DealEnv) -> None:
    view = await env.new_deal()

    impact = await env.impact.execute(view.item.deal.id.value)

    assert impact == DealDeletionImpact(history_count=1, action_count=0, attachment_count=0)


async def test_the_impact_of_another_deal_is_not_counted(env: DealEnv) -> None:
    first = await env.new_deal()
    await env.new_deal()
    await env.update.execute(first.item.deal.id.value, make_patch(name="변경"), SALES)

    other = await env.new_deal()

    assert (await env.impact.execute(other.item.deal.id.value)).history_count == 1


@pytest.mark.parametrize("code", ["20261016-ZZZZ", "not-a-code"])
async def test_the_impact_of_an_unknown_or_malformed_code_is_not_found(
    env: DealEnv, code: str
) -> None:
    with pytest.raises(DealNotFoundError):
        await env.impact.execute(code)
