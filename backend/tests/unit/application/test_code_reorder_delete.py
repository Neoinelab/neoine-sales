"""코드 순서 변경·삭제 유스케이스 (AC-06·07·08).

쓰기 유스케이스는 같은 종류의 행을 잠그고(`list(for_update=True)`) 판단한다.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.application.code.delete_code import DeleteCode
from app.application.code.reorder_codes import ReorderCodes
from app.domain.code.errors import CodeInUseError, CodeLockedError, CodeNotFoundError
from app.domain.code.values import CodeId, CodeKind
from app.domain.common.errors import InvalidValueError
from tests.support.catalog import add_deals_with_status, code_by_key

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWorkFactory
    from tests.fakes.unit_of_work import FakeUnitOfWork, FixedClock

LOCKED = [
    (CodeKind.STATUS, "prospecting"),
    (CodeKind.STATUS, "contract_completed"),
    (CodeKind.FORECAST, "pipeline"),
    (CodeKind.FORECAST, "won"),
    (CodeKind.FORECAST, "lost"),
]


async def _ids(uow: FakeUnitOfWork, kind: CodeKind) -> list[CodeId]:
    return [c.id for c in await uow.codes.list(kind)]


async def _orders(uow: FakeUnitOfWork, kind: CodeKind) -> list[tuple[str, int]]:
    return [(c.key.value, c.order) for c in await uow.codes.list(kind)]


# --- ReorderCodes (AC-06) ---


async def test_reorder_codes_renumbers_from_one_and_returns_the_new_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    reversed_ids = list(reversed(await _ids(seeded, CodeKind.STATUS)))

    result = await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, reversed_ids)

    assert [u.code.id for u in result] == reversed_ids
    assert [u.code.order for u in result] == [1, 2, 3, 4, 5, 6, 7]
    assert await _ids(seeded, CodeKind.STATUS) == reversed_ids


async def test_reorder_codes_updates_only_the_rows_whose_order_changed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    ids = await _ids(seeded, CodeKind.STATUS)
    swapped = [*ids[:5], ids[6], ids[5]]  # 마지막 둘만 자리를 바꾼다
    before = {c.id: c.updated_at for c in await seeded.codes.list(CodeKind.STATUS)}
    clock.advance(60)

    await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, swapped)

    after = {c.id: c.updated_at for c in await seeded.codes.list(CodeKind.STATUS)}
    assert {i for i in ids if after[i] != before[i]} == {ids[5], ids[6]}


async def test_reorder_codes_leaves_the_other_kind_untouched(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    forecasts_before = await _orders(seeded, CodeKind.FORECAST)
    reversed_ids = list(reversed(await _ids(seeded, CodeKind.STATUS)))

    await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, reversed_ids)

    assert await _orders(seeded, CodeKind.FORECAST) == forecasts_before


async def test_reorder_codes_closes_gaps_in_the_order_numbers(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    middle = await code_by_key(seeded, CodeKind.STATUS, "introduction")
    await seeded.codes.delete(middle.id)

    await ReorderCodes(uow_factory, clock).execute(
        CodeKind.STATUS, await _ids(seeded, CodeKind.STATUS)
    )

    assert [order for _, order in await _orders(seeded, CodeKind.STATUS)] == [1, 2, 3, 4, 5, 6]


async def test_reorder_codes_with_a_missing_id_is_rejected_and_keeps_the_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    before = await _orders(seeded, CodeKind.STATUS)
    ids = await _ids(seeded, CodeKind.STATUS)

    with pytest.raises(InvalidValueError) as raised:
        await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, ids[:-1])

    assert str(raised.value) == "순서 목록이 올바르지 않습니다."
    assert await _orders(seeded, CodeKind.STATUS) == before


async def test_reorder_codes_with_a_duplicate_id_is_rejected(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    ids = await _ids(seeded, CodeKind.STATUS)

    with pytest.raises(InvalidValueError):
        await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, [*ids[:-1], ids[0]])


async def test_reorder_codes_with_an_id_of_the_other_kind_is_rejected(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    ids = await _ids(seeded, CodeKind.STATUS)
    foreign = (await _ids(seeded, CodeKind.FORECAST))[0]

    with pytest.raises(InvalidValueError):
        await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, [*ids[:-1], foreign])


# --- DeleteCode (AC-07·08) ---


@pytest.mark.parametrize(("kind", "key"), LOCKED)
async def test_delete_locked_code_raises_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, kind: CodeKind, key: str
) -> None:
    code = await code_by_key(seeded, kind, key)

    with pytest.raises(CodeLockedError):
        await DeleteCode(uow_factory).execute(code.id)

    assert await seeded.codes.get(code.id) == code


async def test_delete_code_in_use_raises_with_the_count_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await add_deals_with_status(seeded, "poc_preparation", 2)
    code = await code_by_key(seeded, CodeKind.STATUS, "poc_preparation")

    with pytest.raises(CodeInUseError) as raised:
        await DeleteCode(uow_factory).execute(code.id)

    assert str(raised.value) == "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"
    assert await seeded.codes.get(code.id) == code


async def test_delete_forecast_code_in_use_raises(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    seeded.deals.forecast_counts = {"best": 1}
    code = await code_by_key(seeded, CodeKind.FORECAST, "best")

    with pytest.raises(CodeInUseError):
        await DeleteCode(uow_factory).execute(code.id)


async def test_delete_locked_code_in_use_reports_locked(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await add_deals_with_status(seeded, "prospecting", 1)
    code = await code_by_key(seeded, CodeKind.STATUS, "prospecting")

    with pytest.raises(CodeLockedError):
        await DeleteCode(uow_factory).execute(code.id)


async def test_delete_unused_unlocked_code_removes_it_and_keeps_the_others(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    code = await code_by_key(seeded, CodeKind.STATUS, "poc_completed")
    others = [i for i in await _ids(seeded, CodeKind.STATUS) if i != code.id]

    await DeleteCode(uow_factory).execute(code.id)

    assert await _ids(seeded, CodeKind.STATUS) == others
    with pytest.raises(CodeNotFoundError):
        await seeded.codes.get(code.id)


async def test_delete_code_ignores_deals_in_other_statuses(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    await add_deals_with_status(seeded, "introduction", 3)
    code = await code_by_key(seeded, CodeKind.STATUS, "poc_completed")

    await DeleteCode(uow_factory).execute(code.id)

    with pytest.raises(CodeNotFoundError):
        await seeded.codes.get(code.id)


async def test_delete_missing_code_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    with pytest.raises(CodeNotFoundError):
        await DeleteCode(uow_factory).execute(CodeId(uuid4()))
