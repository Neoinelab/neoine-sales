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
    """레거시 빈 Solution Deal은 Solution 없는 수정이 되고 Solution은 빈 값 그대로다.

    테스트 코드: DE-054
    """
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)

    # when: 이름과 Users count만 보내 수정한다.
    await env.update.execute(code, make_patch(name="다른 이름", users=3), SALES)

    # then: 수정되고 Solution이 ''로 그대로다.
    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.name, stored.details.users, stored.details.solution) == (
        "다른 이름",
        3,
        "",
    )


async def test_patch_vendor_only_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal에서 Vendor만 바꿔도 성공한다.

    테스트 코드: DE-054
    """
    # given: Solution이 ''인 Deal과 SAP.
    sap = await env.new_vendor("SAP")
    code = await new_legacy_deal(env)

    # when: Vendor만 보낸다.
    await env.update.execute(code, make_patch(vendor_id=sap.id), SALES)

    # then: Vendor가 바뀌고 Solution은 ''다.
    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.vendor_id, stored.details.solution) == (sap.id, "")


async def test_patch_revenue_and_expected_close_succeed_on_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal에서 금액·Expected Close를 고쳐도 성공한다.

    테스트 코드: DE-054
    """
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)

    # when: 금액과 Expected Close만 보낸다.
    await env.update.execute(
        code, make_patch(revenue_amount=5_000, revenue_date=date(2027, 3, 1)), SALES
    )

    # then: 두 값이 바뀐다.
    stored = await env.uow.deals.get(DealCode(code))
    assert (stored.details.revenue_amount.value, stored.details.revenue_date) == (
        5_000,
        date(2027, 3, 1),
    )


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_patch_blank_solution_is_still_rejected_on_a_legacy_deal(
    env: DealEnv, sent: str | None
) -> None:
    """레거시 빈 Solution Deal이라도 빈 Solution을 보내면 거절한다.

    테스트 코드: DE-054
    """
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)

    # when: null, '', '   '를 보낸다.
    with raises_with(InvalidValueError, REQUIRED):
        await env.update.execute(code, make_patch(solution=sent), SALES)

    # then: 'Solution을 입력하세요.' 오류이고 ''로 그대로다.
    assert await _stored_solution(env, code) == ""


async def test_patch_real_solution_fills_in_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal에 실제 Solution을 채울 수 있다.

    테스트 코드: DE-054
    """
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)

    # when: ' ITDR '를 보낸다.
    await env.update.execute(code, make_patch(solution=" ITDR "), SALES)

    # then: Solution이 'ITDR'로 저장된다.
    assert await _stored_solution(env, code) == "ITDR"


async def test_register_without_solution_is_still_rejected(env: DealEnv) -> None:
    """빈 Solution 등록은 여전히 거절한다.

    테스트 코드: DE-017
    """
    # when·then: Solution ''로 등록한다 → 'Solution을 입력하세요.' 오류다.
    with raises_with(InvalidValueError, REQUIRED):
        await env.register.execute(make_create_input(solution=""), SALES)


async def test_apply_revenue_amount_change_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal의 금액 단일 변경은 성공한다(변경 적용은 DD 소유)."""
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    # when: 금액 단일 변경을 적용한다.
    await env.apply.execute(code, DealChangeInput(field="revenue_amount", value=777), SALES)

    # then: 금액이 777로 바뀌고 Solution은 ''다.
    deal = await env.uow.deals.get(DealCode(code))
    assert (deal.details.revenue_amount.value, deal.details.solution) == (777, "")


async def test_apply_status_change_succeeds_on_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal의 Status 단일 변경은 성공한다(변경 적용은 DD 소유)."""
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    # when: Status 단일 변경을 적용한다.
    await env.apply.execute(code, DealChangeInput(field="status_key", value="introduction"), SALES)

    # then: Status가 바뀌고 Solution은 ''다.
    deal = await env.uow.deals.get(DealCode(code))
    assert (deal.sync.status_key, deal.details.solution) == ("introduction", "")


async def test_apply_closing_change_writes_revenue_on_a_legacy_deal(env: DealEnv) -> None:
    """레거시 빈 Solution Deal을 Won으로 닫으면 매출이 채워진다(변경 적용은 DD 소유)."""
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(env)
    from app.application.deal.inputs import DealChangeInput  # noqa: PLC0415

    # when: Won으로 종결 변경을 적용한다.
    await env.apply.execute(
        code, DealChangeInput(field="forecast_key", value="won", resolution=CLOSING), SALES
    )

    # then: Won이 되고 금액·날짜가 확정값이다.
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
    """레거시 빈 Solution Deal에 Status 동기화가 든 Action을 등록해도 성공한다(AC 소유)."""
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(action_env.env)

    # when: Status 변경이 든 Action을 등록한다.
    await action_env.act(
        KIM,
        code=code,
        status_changes=(StatusChangeInput("status_key", "introduction", None),),
    )

    # then: Status가 바뀌고 Solution은 ''다.
    deal = await action_env.env.uow.deals.get(DealCode(code))
    assert (deal.sync.status_key, deal.details.solution) == ("introduction", "")


async def test_action_registration_closing_the_deal_succeeds_on_a_legacy_deal(
    action_env: ActionEnv,
) -> None:
    """레거시 빈 Solution Deal을 Action으로 닫아도 성공한다(AC 소유)."""
    # given: Solution이 ''인 Deal.
    code = await new_legacy_deal(action_env.env)

    # when: Won 종결이 든 Action을 등록한다.
    await action_env.act(
        KIM,
        code=code,
        status_changes=(StatusChangeInput("forecast_key", "won", CLOSING),),
    )

    # then: Won이 되고 금액이 확정값이다.
    deal = await action_env.env.uow.deals.get(DealCode(code))
    assert (deal.sync.forecast_key, deal.details.revenue_amount.value) == ("won", 900_000_000)
