"""UpdateDeal의 Product 텍스트(2026-11-13 변경): 보낸 값만 바꾸고 비울 수 있다(빈 값 '')."""

from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv


async def test_patch_product_replaces_text(env: DealEnv) -> None:
    """Product를 바꾸면 앞뒤 공백을 지워 저장한다.

    테스트 코드: DE-051
    """
    # given: Product 'MFA'인 Deal.
    view = await env.new_deal(product="MFA")

    # when: '  ITDR '로 고친다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(product="  ITDR "), SALES
    )

    # then: 응답과 저장된 값이 'ITDR'이다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert updated.item.deal.details.product == "ITDR"
    assert stored.details.product == "ITDR"


@pytest.mark.parametrize("sent", [None, "", "   "])
async def test_patch_blank_or_null_product_clears_it_and_writes_history(
    env: DealEnv, sent: str | None
) -> None:
    """Product를 null·빈 값·공백으로 고치면 빈 값이 되고 이력이 남는다.

    테스트 코드: DE-052
    """
    # given: Product 'ITDR'인 Deal.
    view = await env.new_deal(product="ITDR")

    # when: null, '', '   '를 보낸다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(product=sent), SALES)

    # then: 오류 없이 저장된 값이 ''이고 Product 이력이 ITDR -> '-'로 남는다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.details.product == ""
    assert await env.changes(updated) == [("other", "Product", "ITDR", "-")]


async def test_patch_too_long_product_is_rejected(env: DealEnv) -> None:
    """201자 Product로 고치면 거절한다.

    테스트 코드: DE-052
    """
    # given: Product 'ITDR'인 Deal.
    view = await env.new_deal(product="ITDR")

    # when·then: 201자 Product를 보낸다 → 'Product는 200자 이내로 입력하세요.' 오류다.
    with raises_with(InvalidValueError, "Product는 200자 이내로 입력하세요."):
        await env.update.execute(view.item.deal.id.value, make_patch(product="a" * 201), SALES)

    # then: 값이 그대로다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.details.product == "ITDR"


async def test_patch_without_product_keeps_text(env: DealEnv) -> None:
    """Product를 보내지 않으면 그대로다.

    테스트 코드: DE-053
    """
    # given: Product 'ITDR'인 Deal.
    view = await env.new_deal(product="ITDR")

    # when: 이름만 보낸다.
    await env.update.execute(view.item.deal.id.value, make_patch(name="다른 이름"), SALES)

    # then: Product가 'ITDR' 그대로다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.name, stored.details.product) == ("다른 이름", "ITDR")


async def test_patch_vendor_only_keeps_product(env: DealEnv) -> None:
    """Vendor만 바꿔도 Product는 그대로다.

    테스트 코드: DE-049
    """
    # given: SAP Vendor·Product 'ITDR'인 Deal.
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=sap.id, product="ITDR")

    # when: Oracle로 Vendor만 바꾼다.
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES)

    # then: Vendor는 Oracle, Product는 'ITDR'이다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.product) == (oracle.id, "ITDR")


async def test_patch_without_product_keeps_an_empty_product(env: DealEnv) -> None:
    """Product가 빈 Deal도 Product를 보내지 않은 수정은 성공하고 빈 값 그대로다.

    테스트 코드: DE-053
    """
    # given: Product가 ''인 Deal.
    view = await env.new_deal(product="")

    # when: 이름과 Users count만 보내 수정한다.
    await env.update.execute(view.item.deal.id.value, make_patch(name="다른 이름", users=3), SALES)

    # then: 수정되고 Product는 ''다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.name, stored.details.users, stored.details.product) == (
        "다른 이름",
        3,
        "",
    )


async def test_patch_vendor_only_succeeds_on_an_empty_product_deal(env: DealEnv) -> None:
    """Product가 빈 Deal에서 Vendor만 바꿔도 성공하고 Product는 빈 값 그대로다.

    테스트 코드: DE-053
    """
    # given: Product가 ''인 Deal과 Oracle.
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(product="")

    # when: Vendor만 보낸다.
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES)

    # then: Vendor가 바뀌고 Product는 ''다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.product) == (oracle.id, "")


async def test_patch_product_fills_in_an_empty_product_deal(env: DealEnv) -> None:
    """Product가 빈 Deal에 나중에 Product를 입력할 수 있고 이력이 남는다.

    테스트 코드: DE-053
    """
    # given: Product가 ''인 Deal.
    view = await env.new_deal(product="")

    # when: ' ITDR '를 보낸다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(product=" ITDR "), SALES)

    # then: Product가 'ITDR'로 저장되고 이력이 '-' -> ITDR로 남는다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert stored.details.product == "ITDR"
    assert await env.changes(updated) == [("other", "Product", "-", "ITDR")]


async def test_patch_product_writes_history(env: DealEnv) -> None:
    """Product를 바꾸면 이전·이후가 이력으로 남는다.

    테스트 코드: DE-051
    """
    # given: Product 'MFA'인 Deal.
    view = await env.new_deal(product="MFA")

    # when: 'ITDR'로 고친다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(product="ITDR"), SALES)

    # then: Product 이력이 MFA -> ITDR로 남는다.
    assert await env.changes(updated) == [("other", "Product", "MFA", "ITDR")]


async def test_patch_same_product_with_surrounding_spaces_leaves_no_history(
    env: DealEnv,
) -> None:
    """앞뒤 공백만 다른 Product는 변경이 아니라 이력이 없다.

    테스트 코드: DE-051
    """
    # given: Product 'ITDR'인 Deal.
    view = await env.new_deal(product="ITDR")

    # when: ' ITDR '를 보낸다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(product=" ITDR "), SALES)

    # then: 이력이 없다.
    assert await env.changes(updated) == []


async def test_patch_case_only_change_of_product_writes_history(env: DealEnv) -> None:
    """Product의 대소문자만 바꿔도 변경이고 이력이 남는다.

    테스트 코드: DE-051
    """
    # given: Product가 'itdr'인 Deal
    view = await env.new_deal(product="itdr")

    # when: 'ITDR'로 고친다
    updated = await env.update.execute(view.item.deal.id.value, make_patch(product="ITDR"), SALES)

    # then: 저장된 값이 'ITDR'이고 Product 이력이 1건 남는다
    assert (await env.uow.deals.get(view.item.deal.id)).details.product == "ITDR"
    assert await env.changes(updated) == [("other", "Product", "itdr", "ITDR")]
