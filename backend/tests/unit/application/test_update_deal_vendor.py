"""UpdateDeal의 Vendor 선택(AC-3·8·9·11): 등록 목록 확인, 비우기, History 이름 표기.

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
    sap = await env.new_vendor("SAP")
    view = await env.new_deal()

    updated = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    assert updated.vendor == NamedRef(sap.id, "SAP")
    assert await env.changes(updated) == [("other", "Vendor", "선택 안 함", "SAP")]


async def test_changing_the_vendor_records_only_the_vendor_entry(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    oracle = await env.new_vendor("Oracle")
    view = await env.new_deal(vendor_id=sap.id, solution="S/4HANA")

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES
    )

    assert updated.vendor == NamedRef(oracle.id, "Oracle")
    assert await env.changes(updated) == [("other", "Vendor", "SAP", "Oracle")]


async def test_clearing_the_vendor_succeeds_and_keeps_the_solution(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id, solution="S/4HANA")

    cleared = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert cleared.vendor is None
    assert (stored.details.vendor_id, stored.details.solution) == (None, "S/4HANA")


async def test_unknown_vendor_is_rejected(env: DealEnv) -> None:
    view = await env.new_deal()

    with raises_with(InvalidValueError, UNKNOWN_VENDOR):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=new_id()), SALES)


async def test_the_same_vendor_again_leaves_no_history(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    view = await env.new_deal(vendor_id=sap.id)

    updated = await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    assert await env.changes(updated) == []


async def test_renamed_vendor_shows_new_name_on_deal_and_keeps_old_history(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP")
    view = await env.new_deal()
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    await RenameVendor(env.uow_factory, env.clock).execute(sap.id, "SAP Korea")

    shown = await env.get.execute(view.item.deal.id.value)
    assert shown.vendor == NamedRef(sap.id, "SAP Korea")
    assert await env.history_rows(view.item.deal.id.value) == [
        ("created", "Deal 등록", "", "Deal 등록"),
        ("other", "Vendor", "선택 안 함", "SAP"),
    ]
