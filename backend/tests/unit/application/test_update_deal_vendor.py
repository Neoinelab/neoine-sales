"""UpdateDeal의 Vendor 선택: 등록 목록 확인, 비울 수 없음(필수), History 이름 표기.

Solution은 Vendor와 독립인 자유 텍스트다(결정 D4). Vendor를 바꿔도 Solution은 그대로다.
"""

from typing import TYPE_CHECKING

from app.application.deal.dto import NamedRef
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.default_vendor import DEFAULT_VENDOR_ID
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

VENDOR_REQUIRED = "Vendor를 선택하세요."
UNKNOWN_VENDOR = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."


async def test_choosing_a_vendor_is_saved_named_and_recorded(env: DealEnv) -> None:
    """다른 Vendor를 고르면 저장되고 이전 Vendor 이름으로 이력이 남는다.

    테스트 코드: DE-049
    """
    # given: Oracle을 고른 Deal과 SAP.
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=oracle.id)

    # when: SAP를 고른다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    # then: 응답 vendor가 {id, SAP}이고 Vendor 이력 1건이다.
    assert updated.vendor == NamedRef(sap.id, "SAP")
    assert await env.changes(updated) == [("other", "Vendor", "Oracle", "SAP")]


async def test_changing_the_vendor_records_only_the_vendor_entry(env: DealEnv) -> None:
    """Vendor를 바꾸면 Vendor 이력만 남는다.

    테스트 코드: DE-049
    """
    # given: SAP·Solution 'S/4HANA'인 Deal과 Oracle.
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=sap.id, solution="S/4HANA")

    # when: Oracle로 바꾼다.
    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES
    )

    # then: Vendor 이력 SAP -> Oracle 1건만 남는다.
    assert updated.vendor == NamedRef(oracle.id, "Oracle")
    assert await env.changes(updated) == [("other", "Vendor", "SAP", "Oracle")]


async def test_clearing_the_vendor_is_rejected_and_keeps_vendor_and_solution(
    env: DealEnv,
) -> None:
    """vendor_id를 null로 보내면 "Vendor를 선택하세요."로 거절되고 Vendor·Solution이 그대로다.

    테스트 코드: DE-116
    """
    # given: SAP·Solution 'S/4HANA'인 Deal.
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id, solution="S/4HANA")

    # when·then: vendor_id를 null로 보낸다 → 'Vendor를 선택하세요.' 오류다.
    with raises_with(InvalidValueError, VENDOR_REQUIRED):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    # then: Vendor·Solution이 그대로고 이력이 없다.
    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution) == (sap.id, "S/4HANA")
    assert await env.changes(view) == []


async def test_null_vendor_is_judged_after_the_name_and_before_the_solution(
    env: DealEnv,
) -> None:
    """vendor_id null은 Deal Name 다음, Solution 앞에서 판정된다.

    테스트 코드: DE-116
    """
    # given: Deal 하나.
    view = await env.new_deal()
    code = view.item.deal.id.value

    # when·then: 빈 이름과 null Vendor를 함께 보낸다 → Deal Name 문구가 먼저다.
    with raises_with(InvalidValueError, "Deal Name을 입력하세요."):
        await env.update.execute(code, make_patch(name="  ", vendor_id=None), SALES)
    # when·then: null Vendor와 201자 Solution을 함께 보낸다 → Vendor 문구가 먼저다.
    with raises_with(InvalidValueError, VENDOR_REQUIRED):
        await env.update.execute(code, make_patch(vendor_id=None, solution="a" * 201), SALES)


async def test_unknown_vendor_is_rejected(env: DealEnv) -> None:
    """없는 Vendor id로 고치면 거절되고 Vendor는 그대로다.

    테스트 코드: DE-050
    """
    # given: 기본 Vendor를 고른 Deal.
    view = await env.new_deal()

    # when·then: 없는 Vendor id를 보낸다
    #   → '선택한 Vendor가 없습니다…' 오류이고 Vendor·이력이 그대로다.
    with raises_with(InvalidValueError, UNKNOWN_VENDOR):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=new_id()), SALES)

    assert (await env.uow.deals.get(view.item.deal.id)).details.vendor_id == DEFAULT_VENDOR_ID
    assert await env.changes(view) == []


async def test_the_same_vendor_again_leaves_no_history(env: DealEnv) -> None:
    """같은 Vendor를 다시 보내면 이력이 없다.

    테스트 코드: DE-049
    """
    # given: SAP를 고른 Deal.
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id)

    # when: SAP를 다시 보낸다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    # then: 이력이 없다.
    assert await env.changes(updated) == []


async def test_renamed_vendor_shows_new_name_on_deal_and_keeps_old_history(env: DealEnv) -> None:
    """Vendor 이름을 바꾸면 그 Vendor를 쓰는 Deal은 새 이름을 보이고 History는 그대로다.

    테스트 코드: CL-058
    """
    # given: 'SAP' Vendor를 고른 Deal이 있고 그 변경 History가 남았다
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=oracle.id)
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    # when: Vendor를 'SAP Korea'로 바꾼다
    await RenameVendor(env.uow_factory, env.clock).execute(sap.id, "SAP Korea")

    # then: Deal의 Vendor는 같은 id에 새 이름이고 History는 'SAP' 그대로다
    shown = await env.get.execute(view.item.deal.id.value)
    assert shown.vendor == NamedRef(sap.id, "SAP Korea")
    assert await env.history_rows(view.item.deal.id.value) == [
        ("created", "Deal 등록", "", "Deal 등록"),
        ("other", "Vendor", "Oracle", "SAP"),
    ]
