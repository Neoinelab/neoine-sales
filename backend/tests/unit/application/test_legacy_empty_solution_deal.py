"""레거시 빈 Solution(`''`) Deal(리뷰 후속 결정): Solution을 보내지 않은 변경은 허용한다.

빈 값 거절은 입력 경로에서 solution을 보낸 경우에만 한다(등록은 항상 필수, 수정은 보낸 때만).
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.application.deal_action.inputs import StatusChangeInput
from app.domain.common.errors import InvalidValueError
from app.domain.deal.code import DealCode
from tests.factories_deal import SALES, make_create_input, make_patch
from tests.support.expect import raises_with
from tests.support.legacy_solution import new_legacy_deal
from tests.unit.application.action_env import KIM
from tests.unit.application.apply_helpers import CLOSING, DAY

if TYPE_CHECKING:
    from tests.unit.application.action_env import ActionEnv
    from tests.unit.application.deal_env import DealEnv

REQUIRED = "Solution을 입력하세요."


async def _stored_solution(env: DealEnv, code: str) -> str:
    return (await env.uow.deals.get(DealCode(code))).details.solution


async def test_patch_without_solution_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)

    await env.update.execute(code, make_patch(name="다른 이름", users=3), SALES)

    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.name, stored.details.users, stored.details.solution) == (
        "다른 이름",
        3,
        "",
    )


async def test_patch_vendor_only_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    code = await new_legacy_deal(env)

    await env.update.execute(code, make_patch(vendor_id=sap.id), SALES)

    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.vendor_id, stored.details.solution) == (sap.id, "")


async def test_patch_revenue_and_expected_close_succeed_on_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)

    await env.update.execute(
        code, make_patch(revenue_amount=5_000, revenue_date=date(2027, 3, 1)), SALES
    )

    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.revenue_amount.value, stored.details.revenue_date) == (
        5_000,
        date(2027, 3, 1),
    )


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_patch_blank_solution_is_still_rejected_on_a_legacy_deal(
    env: DealEnv, sent: str | None
) -> None:
    code = await new_legacy_deal(env)

    with raises_with(InvalidValueError, REQUIRED):
        await env.update.execute(code, make_patch(solution=sent), SALES)

    assert await _stored_solution(env, code) == ""


async def test_patch_real_solution_fills_in_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)

    await env.update.execute(code, make_patch(solution=" ITDR "), SALES)

    assert await _stored_solution(env, code) == "ITDR"


async def test_register_without_solution_is_still_rejected(env: DealEnv) -> None:
    with raises_with(InvalidValueError, REQUIRED):
        await env.register.execute(make_create_input(solution=""), SALES)


async def test_apply_revenue_amount_change_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    await env.apply.execute(code, DealChangeInput(field="revenue_amount", value=777), SALES)

    deal = await env.uow.deals.get(DealCode(code))
    assert (deal.details.revenue_amount.value, deal.details.solution) == (777, "")


async def test_apply_status_change_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    await env.apply.execute(code, DealChangeInput(field="status_key", value="introduction"), SALES)

    deal = await env.uow.deals.get(DealCode(code))
    assert (deal.sync.status_key, deal.details.solution) == ("introduction", "")


async def test_apply_closing_change_writes_revenue_on_a_legacy_deal(env: DealEnv) -> None:
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    await env.apply.execute(
        code, DealChangeInput(field="forecast_key", value="won", resolution=CLOSING), SALES
    )

    deal = await env.uow.deals.get(DealCode(code))
    assert (
        deal.sync.forecast_key,
        deal.details.revenue_amount.value,
        deal.details.revenue_date,
    ) == (
        "won",
        900_000_000,
        DAY,
    )
    assert deal.details.solution == ""


async def test_action_registration_with_status_sync_succeeds_on_a_legacy_deal(
    action_env: ActionEnv,
) -> None:
    code = await new_legacy_deal(action_env.env)

    await action_env.act(
        KIM,
        code=code,
        status_changes=(StatusChangeInput("status_key", "introduction", None),),
    )

    deal = await action_env.env.uow.deals.get(DealCode(code))
    assert (deal.sync.status_key, deal.details.solution) == ("introduction", "")


async def test_action_registration_closing_the_deal_succeeds_on_a_legacy_deal(
    action_env: ActionEnv,
) -> None:
    code = await new_legacy_deal(action_env.env)

    await action_env.act(
        KIM,
        code=code,
        status_changes=(StatusChangeInput("forecast_key", "won", CLOSING),),
    )

    deal = await action_env.env.uow.deals.get(DealCode(code))
    assert (deal.sync.forecast_key, deal.details.revenue_amount.value) == ("won", 900_000_000)
