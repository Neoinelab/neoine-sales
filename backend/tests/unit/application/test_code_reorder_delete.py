"""코드 순서 변경·삭제 유스케이스 (CD-031~040, CD-045).

쓰기 유스케이스는 같은 종류의 행을 잠그고(`list(for_update=True)`) 판단한다.
"""

from typing import TYPE_CHECKING

import pytest

from app.application.code.delete_code import DeleteCode
from app.application.code.reorder_codes import ReorderCodes
from app.domain.code.errors import CodeInUseError, CodeLockedError, CodeNotFoundError
from app.domain.code.values import CodeId, CodeKind
from app.domain.common.errors import InvalidValueError
from tests.support.catalog import add_deals_with_status, code_by_key
from tests.support.expect import raises_with
from tests.support.ids import new_id

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


REORDER_MESSAGE = "순서 목록이 올바르지 않습니다."
LOCKED_MESSAGE = "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."


async def _ids(uow: FakeUnitOfWork, kind: CodeKind) -> list[CodeId]:
    return [c.id for c in await uow.codes.list(kind)]


async def _orders(uow: FakeUnitOfWork, kind: CodeKind) -> list[tuple[str, int]]:
    return [(c.key.value, c.order) for c in await uow.codes.list(kind)]


# --- ReorderCodes ---


@pytest.mark.parametrize("kind", [CodeKind.STATUS, CodeKind.FORECAST])
async def test_reorder_codes_renumbers_from_one_and_returns_the_new_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, kind: CodeKind
) -> None:
    """전체 id 목록으로 순서를 바꾸면 1부터 다시 매긴 새 순서가 돌아오고 조회도 그 순서다.

    테스트 코드: CD-031
    """
    # given: 기본 코드와 그 종류 전체 id를 거꾸로 한 목록
    reversed_ids = list(reversed(await _ids(seeded, kind)))

    # when: 순서를 바꾼다
    result = await ReorderCodes(uow_factory, clock).execute(kind, reversed_ids)

    # then: 응답이 보낸 순서이고 order는 1부터이며 저장소 조회도 같은 순서다
    assert [u.code.id for u in result] == reversed_ids
    assert [u.code.order for u in result] == list(range(1, len(reversed_ids) + 1))
    assert [u.usage_count for u in result] == [0] * len(reversed_ids)
    assert await _ids(seeded, kind) == reversed_ids


async def test_reorder_codes_updates_only_the_rows_whose_order_changed(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """순서 변경은 순서가 바뀐 코드만 변경 시각을 갱신한다.

    테스트 코드: CD-032
    """
    # given: 시계를 60초 앞으로 돌리고, 마지막 둘만 자리를 바꾼 전체 목록을 준비한다
    ids = await _ids(seeded, CodeKind.STATUS)
    swapped = [*ids[:5], ids[6], ids[5]]
    before = {c.id: c.updated_at for c in await seeded.codes.list(CodeKind.STATUS)}
    clock.advance(60)

    # when: 순서를 바꾼다
    await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, swapped)

    # then: 그 두 코드만 변경 시각이 바뀐다
    after = {c.id: c.updated_at for c in await seeded.codes.list(CodeKind.STATUS)}
    assert {i for i in ids if after[i] != before[i]} == {ids[5], ids[6]}
    assert after[ids[5]] == after[ids[6]] == clock.now()


async def test_reorder_codes_leaves_the_other_kind_untouched(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """한 종류의 순서를 바꿔도 다른 종류는 그대로다.

    테스트 코드: CD-033
    """
    # given: Forecast의 (key, order)와 거꾸로 된 Status 전체 id 목록
    forecasts_before = await _orders(seeded, CodeKind.FORECAST)
    reversed_ids = list(reversed(await _ids(seeded, CodeKind.STATUS)))

    # when: Status 순서를 바꾼다
    await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, reversed_ids)

    # then: Forecast는 바뀌기 전과 같다
    assert await _orders(seeded, CodeKind.FORECAST) == forecasts_before


async def test_reorder_codes_closes_gaps_in_the_order_numbers(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """순서 변경은 삭제로 생긴 빈 번호를 메운다.

    테스트 코드: CD-034
    """
    # given: 제품소개를 지워 order 2가 비어 있다
    middle = await code_by_key(seeded, CodeKind.STATUS, "introduction")
    await seeded.codes.delete(middle.id)

    # when: 남은 Status 6개를 지금 순서대로 보낸다
    await ReorderCodes(uow_factory, clock).execute(
        CodeKind.STATUS, await _ids(seeded, CodeKind.STATUS)
    )

    # then: order가 1~6이다
    assert [order for _, order in await _orders(seeded, CodeKind.STATUS)] == [1, 2, 3, 4, 5, 6]


async def _invalid_status_lists(uow: FakeUnitOfWork) -> dict[str, list[CodeId]]:
    ids = await _ids(uow, CodeKind.STATUS)
    foreign = (await _ids(uow, CodeKind.FORECAST))[0]
    return {
        "missing": ids[:-1],
        "duplicate": [*ids[:-1], ids[0]],
        "other-kind": [*ids[:-1], foreign],
        "unknown": [*ids[:-1], CodeId(new_id())],
        "empty": [],
    }


@pytest.mark.parametrize("case", ["missing", "duplicate", "other-kind", "unknown", "empty"])
async def test_reorder_codes_with_an_invalid_list_is_rejected_and_keeps_the_order(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock, case: str
) -> None:
    """빠진·중복·다른 종류·없는·빈 id 목록은 거절하고 순서는 그대로다.

    테스트 코드: CD-035
    """
    # given: 잘못된 Status 순서 목록(마지막 id 빠짐, 첫 id 중복, Forecast id 섞음, 없는 id, 빈 목록)
    before = await _orders(seeded, CodeKind.STATUS)
    ordered_ids = (await _invalid_status_lists(seeded))[case]

    # when: 순서를 바꾼다
    with raises_with(InvalidValueError, REORDER_MESSAGE):
        await ReorderCodes(uow_factory, clock).execute(CodeKind.STATUS, ordered_ids)

    # then: Status의 (key, order)가 그대로다
    assert await _orders(seeded, CodeKind.STATUS) == before


async def test_reorder_forecast_codes_with_a_status_id_is_rejected(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, clock: FixedClock
) -> None:
    """Forecast 순서 목록에 Status id를 섞으면 거절하고 순서는 그대로다.

    테스트 코드: CD-035
    """
    # given: 마지막 대신 Status id를 넣은 Forecast 목록
    before = await _orders(seeded, CodeKind.FORECAST)
    ids = await _ids(seeded, CodeKind.FORECAST)
    foreign = (await _ids(seeded, CodeKind.STATUS))[0]

    # when: Forecast 순서를 바꾼다
    with raises_with(InvalidValueError, REORDER_MESSAGE):
        await ReorderCodes(uow_factory, clock).execute(CodeKind.FORECAST, [*ids[:-1], foreign])

    # then: Forecast의 (key, order)가 그대로다
    assert await _orders(seeded, CodeKind.FORECAST) == before


# --- DeleteCode ---


@pytest.mark.parametrize(("kind", "key"), LOCKED)
async def test_delete_locked_code_raises_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory, kind: CodeKind, key: str
) -> None:
    """잠금 코드는 쓰는 Deal이 없어도 삭제할 수 없고 남는다.

    테스트 코드: CD-037
    """
    # given: 쓰는 Deal이 없는 잠금 코드
    code = await code_by_key(seeded, kind, key)

    # when: 삭제한다
    with raises_with(CodeLockedError, LOCKED_MESSAGE):
        await DeleteCode(uow_factory).execute(code.id)

    # then: 코드는 그대로다
    assert await seeded.codes.get(code.id) == code


async def test_delete_locked_code_in_use_reports_locked(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """잠금 코드를 Deal이 쓰고 있어도 잠금 문구가 먼저다.

    테스트 코드: CD-038
    """
    # given: 기회발굴(잠금)을 쓰는 Deal 1건
    await add_deals_with_status(seeded, "prospecting", 1)
    code = await code_by_key(seeded, CodeKind.STATUS, "prospecting")

    # when: 기회발굴을 삭제한다
    with raises_with(CodeLockedError, LOCKED_MESSAGE):
        await DeleteCode(uow_factory).execute(code.id)

    # then: 코드는 남는다
    assert await seeded.codes.get(code.id) == code


async def test_delete_unused_codes_removes_only_them_and_ignores_other_codes_usage(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """쓰이지 않는 일반 코드는 지워지고 다른 코드를 쓰는 Deal은 영향이 없다.

    테스트 코드: CD-039
    """
    # given: 제품소개를 쓰는 Deal 3건, Commit을 쓰는 Deal이 있다
    await add_deals_with_status(seeded, "introduction", 3)
    seeded.deals.forecast_counts = {"commit": 1}
    targets = [
        await code_by_key(seeded, CodeKind.STATUS, "poc_completed"),
        await code_by_key(seeded, CodeKind.FORECAST, "best"),
        await code_by_key(seeded, CodeKind.STATUS, "technical_evaluation"),
        await code_by_key(seeded, CodeKind.FORECAST, "most_likely"),
    ]
    status_before = await _ids(seeded, CodeKind.STATUS)
    forecast_before = await _ids(seeded, CodeKind.FORECAST)

    # when: 쓰이지 않는 네 코드를 각각 삭제한다
    for target in targets:
        await DeleteCode(uow_factory).execute(target.id)

    # then: 그 코드만 사라지고 남은 id 목록은 지운 것만 빠진 그대로다
    gone = {t.id for t in targets}
    assert await _ids(seeded, CodeKind.STATUS) == [i for i in status_before if i not in gone]
    assert await _ids(seeded, CodeKind.FORECAST) == [i for i in forecast_before if i not in gone]
    for target in targets:
        with pytest.raises(CodeNotFoundError):
            await seeded.codes.get(target.id)


async def test_delete_code_in_use_raises_with_the_count_and_keeps_the_row(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Deal이 쓰는 Status 코드는 삭제할 수 없고 문구에 Deal 수가 들어간다.

    테스트 코드: CD-040
    """
    # given: POC준비를 쓰는 Deal 2건
    await add_deals_with_status(seeded, "poc_preparation", 2)
    code = await code_by_key(seeded, CodeKind.STATUS, "poc_preparation")

    # when: POC준비를 삭제한다
    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)"):
        await DeleteCode(uow_factory).execute(code.id)

    # then: 코드는 남는다
    assert await seeded.codes.get(code.id) == code


async def test_delete_forecast_code_in_use_raises(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """Deal이 쓰는 Forecast 코드는 삭제할 수 없고 문구에 Deal 수가 들어간다.

    테스트 코드: CD-040
    """
    # given: Best를 쓰는 Deal 1건
    seeded.deals.forecast_counts = {"best": 1}
    code = await code_by_key(seeded, CodeKind.FORECAST, "best")

    # when: Best를 삭제한다
    with raises_with(CodeInUseError, "사용 중인 코드는 삭제할 수 없습니다. (Deal 1건)"):
        await DeleteCode(uow_factory).execute(code.id)

    # then: 코드는 남는다
    assert await seeded.codes.get(code.id) == code


async def test_delete_missing_code_raises_not_found(
    seeded: FakeUnitOfWork, uow_factory: UnitOfWorkFactory
) -> None:
    """없는 코드를 지우면 찾을 수 없다.

    테스트 코드: CD-045
    """
    # given: 없는 id
    missing = CodeId(new_id())

    # when: 그 id를 삭제한다
    with pytest.raises(CodeNotFoundError) as raised:
        await DeleteCode(uow_factory).execute(missing)

    # then: 없는 id를 가리키는 오류다
    assert raised.value.identifier == missing
