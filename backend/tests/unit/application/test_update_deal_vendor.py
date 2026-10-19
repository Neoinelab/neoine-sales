"""UpdateDeal의 Vendor·Solution 선택(AC-2·10·12·14): FK 검증, 비우기, History 이름 표기.

서버는 Vendor만 바뀐 PATCH에서 Solution을 자동으로 비우지 않는다(소속 불일치는 422).
비우는 것은 화면이 `solution_id: None`을 함께 보내서 한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

from app.application.deal.dto import NamedRef
from app.application.vendor.rename_vendor import RenameVendor
from app.domain.common.errors import InvalidValueError
from tests.factories_deal import SALES, make_patch
from tests.support.expect import raises_with

if TYPE_CHECKING:
    from tests.unit.application.deal_env import DealEnv

NEEDS_VENDOR = "Solution을 선택하려면 Vendor를 먼저 선택하세요."
UNKNOWN_VENDOR = "선택한 Vendor가 없습니다. 목록에서 다시 선택하세요."
MISMATCH = "선택한 Solution은 이 Vendor에 속하지 않습니다."


async def test_choosing_a_vendor_and_its_solution_is_saved_and_named(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    view = await env.new_deal()

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(vendor_id=sap.id, solution_id=sap.solutions[0].id),
        SALES,
    )

    assert (updated.vendor, updated.solution) == (
        NamedRef(sap.id, "SAP"),
        NamedRef(sap.solutions[0].id, "S/4HANA"),
    )
    assert await env.changes(updated) == [
        ("other", "Vendor", "선택 안 함", "SAP"),
        ("other", "Solution", "선택 안 함", "S/4HANA"),
    ]


async def test_changing_vendor_alone_while_solution_belongs_to_old_vendor_is_rejected(
    env: DealEnv,
) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    oracle = await env.new_vendor("Oracle", ("EBS",))
    view = await env.new_deal(vendor_id=sap.id, solution_id=sap.solutions[0].id)

    with raises_with(InvalidValueError, MISMATCH):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=oracle.id), SALES)

    stored = await env.uow.deals.get(view.item.deal.id)
    assert (stored.details.vendor_id, stored.details.solution_id) == (
        sap.id,
        sap.solutions[0].id,
    )


async def test_changing_vendor_with_null_solution_records_two_history_entries(
    env: DealEnv,
) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    oracle = await env.new_vendor("Oracle", ("EBS",))
    view = await env.new_deal(vendor_id=sap.id, solution_id=sap.solutions[0].id)

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(vendor_id=oracle.id, solution_id=None), SALES
    )

    assert (updated.vendor, updated.solution) == (NamedRef(oracle.id, "Oracle"), None)
    assert await env.changes(updated) == [
        ("other", "Vendor", "SAP", "Oracle"),
        ("other", "Solution", "S/4HANA", "선택 안 함"),
    ]


async def test_clearing_the_vendor_requires_clearing_the_solution_too(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    view = await env.new_deal(vendor_id=sap.id, solution_id=sap.solutions[0].id)

    with raises_with(InvalidValueError, NEEDS_VENDOR):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=None), SALES)

    cleared = await env.update.execute(
        view.item.deal.id.value, make_patch(vendor_id=None, solution_id=None), SALES
    )
    assert (cleared.vendor, cleared.solution) == (None, None)


async def test_sending_only_a_solution_of_the_current_vendor_changes_just_the_solution(
    env: DealEnv,
) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA", "BW"))
    s4, bw = sap.solutions
    view = await env.new_deal(vendor_id=sap.id, solution_id=s4.id)

    updated = await env.update.execute(
        view.item.deal.id.value, make_patch(solution_id=bw.id), SALES
    )

    assert await env.changes(updated) == [("other", "Solution", "S/4HANA", "BW")]


async def test_unknown_vendor_is_rejected(env: DealEnv) -> None:
    view = await env.new_deal()

    with raises_with(InvalidValueError, UNKNOWN_VENDOR):
        await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=uuid4()), SALES)


async def test_solution_without_any_vendor_is_rejected(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    view = await env.new_deal()

    with raises_with(InvalidValueError, NEEDS_VENDOR):
        await env.update.execute(
            view.item.deal.id.value, make_patch(solution_id=sap.solutions[0].id), SALES
        )


async def test_the_same_vendor_again_leaves_no_history(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    view = await env.new_deal(vendor_id=sap.id, solution_id=sap.solutions[0].id)

    updated = await env.update.execute(
        view.item.deal.id.value,
        make_patch(vendor_id=sap.id, solution_id=sap.solutions[0].id),
        SALES,
    )

    assert await env.changes(updated) == []


async def test_renamed_vendor_shows_new_name_on_deal_and_keeps_old_history(env: DealEnv) -> None:
    sap = await env.new_vendor("SAP", ("S/4HANA",))
    view = await env.new_deal()
    await env.update.execute(view.item.deal.id.value, make_patch(vendor_id=sap.id), SALES)

    await RenameVendor(env.uow_factory, env.clock).execute(sap.id, "SAP Korea")

    shown = await env.get.execute(view.item.deal.id.value)
    assert shown.vendor == NamedRef(sap.id, "SAP Korea")
    assert await env.history_rows(view.item.deal.id.value) == [
        ("created", "Deal 등록", "", "Deal 등록"),
        ("other", "Vendor", "선택 안 함", "SAP"),
    ]
