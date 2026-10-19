"""GetDealDeletionImpact(AC-26): 삭제 영향 건수. 필터용 facets는 폐지되었다(Vendor AC-17)."""

import importlib
from typing import TYPE_CHECKING

import pytest

from app.application.deal_action.register_deal_action import RegisterDealAction
from app.application.ports.deal_repository import DealDeletionImpact
from app.domain.deal.errors import DealNotFoundError
from tests.factories import make_register_input
from tests.factories_deal import SALES, make_patch

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


def test_the_facets_use_case_is_gone() -> None:
    """AC-17: Vendor·Solution 선택지는 등록 목록(`/vendors`)에서 오고 Deal에서 모으지 않는다."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.application.deal.list_facets")


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
