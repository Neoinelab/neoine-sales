"""UpdateDeal의 Solution 텍스트(Q1 변경): 보낸 값만 바꾸고 비울 수 없다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

REQUIRED = "Solution을 입력하세요."


async def test_patch_solution_replaces_text(env: DealEnv) -> None:
    """Solution을 바꾸면 앞뒤 공백을 지워 저장한다.

    테스트 코드: DE-051
    """
    # given: Solution 'MFA'인 Deal.
    view = await env.new_deal(solution="MFA")

    # when: '  ITDR '로 고친다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(solution="  ITDR "), SALES
    )

    # then: 응답과 저장된 값이 'ITDR'이다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert updated.item.deal.details.solution == "ITDR"
    assert stored.details.solution == "ITDR"


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_patch_blank_or_null_solution_is_rejected_and_keeps_the_text(
    env: DealEnv, sent: str | None
) -> None:
    """Solution을 null·빈 값·공백으로 고치면 거절되고 그대로다.

    테스트 코드: DE-052
    """
    # given: Solution 'ITDR'인 Deal.
    view = await env.new_deal(solution="ITDR")

    # when: null, '', '   '를 보낸다.
    with raises_with(InvalidValueError, REQUIRED):
        await env.update.execute(view.item.deal.id.value, make_patch(solution=sent), SALES)

    # then: 'Solution을 입력하세요.' 오류이고 값이 그대로다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.details.solution == "ITDR"


async def test_patch_too_long_solution_is_rejected(env: DealEnv) -> None:
    """201자 Solution으로 고치면 거절한다.

    테스트 코드: DE-052
    """
    # given: Solution 'ITDR'인 Deal.
    view = await env.new_deal(solution="ITDR")

    # when·then: 201자 Solution을 보낸다 → 'Solution은 200자 이내로 입력하세요.' 오류다.
    with raises_with(InvalidValueError, "Solution은 200자 이내로 입력하세요."):
        await env.update.execute(view.item.deal.id.value, make_patch(solution="a" * 201), SALES)


async def test_patch_without_solution_keeps_text(env: DealEnv) -> None:
    """Solution을 보내지 않으면 그대로다.

    테스트 코드: DE-053
    """
    # given: Solution 'ITDR'인 Deal.
    view = await env.new_deal(solution="ITDR")

    # when: 이름만 보낸다.
    await env.update.execute(view.item.deal.id.value, make_patch(name="다른 이름"), SALES)

    # then: Solution이 'ITDR' 그대로다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.name, stored.details.solution) == ("다른 이름", "ITDR")


async def test_patch_vendor_only_keeps_solution(env: DealEnv) -> None:
    """Vendor만 바꿔도 Solution은 그대로다.

    테스트 코드: DE-049
    """
    # given: SAP Vendor·Solution 'ITDR'인 Deal.
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=sap.id, solution="ITDR")

    # when: Oracle로 Vendor만 바꾼다.
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES)

    # then: Vendor는 Oracle, Solution은 'ITDR'이다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution) == (oracle.id, "ITDR")


async def test_patch_vendor_null_keeps_solution(env: DealEnv) -> None:
    """Vendor를 비워도 Solution은 그대로다.

    테스트 코드: DE-049
    """
    # given: SAP Vendor·Solution 'ITDR'인 Deal.
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id, solution="ITDR")

    # when: vendor_id를 null로 보낸다.
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    # then: Vendor는 없고 Solution은 'ITDR'이다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution) == (None, "ITDR")


async def test_patch_solution_without_any_vendor_succeeds(env: DealEnv) -> None:
    """Vendor가 없는 Deal에도 Solution을 입력할 수 있다.

    테스트 코드: DE-053
    """
    # given: Vendor 없는 Deal.
    view = await env.new_deal(solution="MFA")

    # when: Solution을 'ITDR'로 고친다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(solution="ITDR"), SALES)

    # then: 수정되고 Vendor는 계속 없다.
    assert updated.vendor is None
    assert updated.item.deal.details.solution == "ITDR"


async def test_patch_solution_writes_history(env: DealEnv) -> None:
    """Solution을 바꾸면 이전·이후가 이력으로 남는다.

    테스트 코드: DE-051
    """
    # given: Solution 'MFA'인 Deal.
    view = await env.new_deal(solution="MFA")

    # when: 'ITDR'로 고친다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(solution="ITDR"), SALES)

    # then: Solution 이력이 MFA -> ITDR로 남는다.
    assert await env.changes(updated) == [("other", "Solution", "MFA", "ITDR")]


async def test_patch_same_solution_with_surrounding_spaces_leaves_no_history(
    env: DealEnv,
) -> None:
    """앞뒤 공백만 다른 Solution은 변경이 아니라 이력이 없다.

    테스트 코드: DE-051
    """
    # given: Solution 'ITDR'인 Deal.
    view = await env.new_deal(solution="ITDR")

    # when: ' ITDR '를 보낸다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(solution=" ITDR "), SALES
    )

    # then: 이력이 없다.
    assert await env.changes(updated) == []


async def test_patch_case_only_change_of_solution_writes_history(env: DealEnv) -> None:
    """Solution의 대소문자만 바꿔도 변경이고 이력이 남는다.

    테스트 코드: DE-051
    """
    # given: Solution이 'itdr'인 Deal
    view = await env.new_deal(solution="itdr")

    # when: 'ITDR'로 고친다
    updated = await env.update.execute(view.item.deal.id.value, make_patch(solution="ITDR"), SALES)

    # then: 저장된 값이 'ITDR'이고 Solution 이력이 1건 남는다
    assert (await env.uow.deals.get(view.item.deal.id)).details.solution == "ITDR"
    assert await env.changes(updated) == [("other", "Solution", "itdr", "ITDR")]
