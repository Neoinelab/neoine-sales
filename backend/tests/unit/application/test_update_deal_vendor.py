"""UpdateDeal의 Vendor 선택: 등록 목록 확인, 비우기, History 이름 표기.

Solution은 Vendor와 독립인 자유 텍스트다(결정 D4). Vendor를 바꾸거나 비워도 Solution은 그대로다.
"""

from typing import TYPE_CHECKING

from app.application.deal.dto import NamedRef
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

UNKNOWN_VENDOR = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."


async def test_choosing_a_vendor_is_saved_named_and_recorded(env: DealEnv) -> None:
    """Vendor를 처음 고르면 저장되고 이전 값 '선택 안 함'으로 이력이 남는다.

    테스트 코드: DE-049
    """
    # given: Vendor 없는 Deal과 SAP.
    sap = await env.new_vendor("SAP")
    view = await env.new_deal()

    # when: SAP를 고른다.
    updated = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    # then: 응답 vendor가 {id, SAP}이고 Vendor 이력 1건이다.
    assert updated.vendor == NamedRef(sap.id, "SAP")
    assert await env.changes(updated) == [("other", "Vendor", "선택 안 함", "SAP")]


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


async def test_clearing_the_vendor_succeeds_and_keeps_the_solution(env: DealEnv) -> None:
    """Vendor를 비우면 Solution은 그대로이다.

    테스트 코드: DE-049
    """
    # given: SAP·Solution 'S/4HANA'인 Deal.
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id, solution="S/4HANA")

    cleared = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    # when: vendor_id를 null로 보낸다.
    stored = await env.uow.deals.get(view.item.deal.id)
    # then: Vendor는 없고 Solution은 그대로다.
    assert cleared.vendor is None
    assert (stored.details.vendor_id, stored.details.solution) == (None, "S/4HANA")


async def test_unknown_vendor_is_rejected(env: DealEnv) -> None:
    """없는 Vendor id로 고치면 거절되고 Vendor는 그대로다.

    테스트 코드: DE-050
    """
    # given: Vendor 없는 Deal.
    view = await env.new_deal()

    # when·then: 없는 Vendor id를 보낸다
    #   → '선택한 Vendor가 없습니다…' 오류이고 Vendor·이력이 그대로다.
    with raises_with(InvalidValueError, UNKNOWN_VENDOR):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=new_id()), SALES)

    assert (await env.uow.deals.get(view.item.deal.id)).details.vendor_id is None
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
    view = await env.new_deal()
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    # when: Vendor를 'SAP Korea'로 바꾼다
    await RenameVendor(env.uow_factory, env.clock).execute(sap.id, "SAP Korea")

    # then: Deal의 Vendor는 같은 id에 새 이름이고 History는 'SAP' 그대로다
    shown = await env.get.execute(view.item.deal.id.value)
    assert shown.vendor == NamedRef(sap.id, "SAP Korea")
    assert await env.history_rows(view.item.deal.id.value) == [
        ("created", "Deal 등록", "", "Deal 등록"),
        ("other", "Vendor", "선택 안 함", "SAP"),
    ]
