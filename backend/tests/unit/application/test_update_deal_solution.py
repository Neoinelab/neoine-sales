"""UpdateDeal의 Solution 텍스트(AC-8·9·11, Q1 변경): 보낸 값만 바꾸고 비울 수 없다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

REQUIRED = "Solution을 입력하세요."


async def test_patch_solution_replaces_text(env: DealEnv) -> None:
    view = await env.new_deal(solution="MFA")

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(solution="  ITDR "), SALES
    )

    stored = await env.uow.deals.get(view.item.deal.id)
    assert updated.item.deal.details.solution == "ITDR"
    assert stored.details.solution == "ITDR"


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_patch_blank_or_null_solution_is_rejected_and_keeps_the_text(
    env: DealEnv, sent: str | None
) -> None:
    view = await env.new_deal(solution="ITDR")

    with raises_with(InvalidValueError, REQUIRED):
        await env.update.execute(view.item.deal.id.value, make_patch(solution=sent), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.details.solution == "ITDR"


async def test_patch_too_long_solution_is_rejected(env: DealEnv) -> None:
    view = await env.new_deal(solution="ITDR")

    with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
        await env.update.execute(view.item.deal.id.value, make_patch(solution="a" * 201), SALES)


async def test_patch_without_solution_keeps_text(env: DealEnv) -> None:
    view = await env.new_deal(solution="ITDR")

    await env.update.execute(view.item.deal.id.value, make_patch(name="다른 이름"), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.name, stored.details.solution) == ("다른 이름", "ITDR")


async def test_patch_vendor_only_keeps_solution(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=sap.id, solution="ITDR")

    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution) == (oracle.id, "ITDR")


async def test_patch_vendor_null_keeps_solution(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id, solution="ITDR")

    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution) == (None, "ITDR")


async def test_patch_solution_without_any_vendor_succeeds(env: DealEnv) -> None:
    view = await env.new_deal(solution="MFA")

    updated = await env.update.execute(view.item.deal.id.value, make_patch(solution="ITDR"), SALES)

    assert updated.vendor is None
    assert updated.item.deal.details.solution == "ITDR"


async def test_patch_solution_writes_history(env: DealEnv) -> None:
    view = await env.new_deal(solution="MFA")

    updated = await env.update.execute(view.item.deal.id.value, make_patch(solution="ITDR"), SALES)

    assert await env.changes(updated) == [("other", "Solution", "MFA", "ITDR")]


async def test_patch_same_solution_with_surrounding_spaces_leaves_no_history(
    env: DealEnv,
) -> None:
    view = await env.new_deal(solution="ITDR")

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(solution=" ITDR "), SALES
    )

    assert await env.changes(updated) == []
