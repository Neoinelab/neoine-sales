"""DealActionRepository 계약(저장·수정·삭제·참조): Fake와 SQL(PostgreSQL)에 같은 테스트."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.errors import DealActionNotFoundError
from tests.factories import (
    later,
    make_action_content,
    make_deal_action,
    make_deal_code,
    make_sync,
)
from tests.factories_action_type import attach_catalog_type, make_action_type, make_type_ref
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.deal_action_case import Case


async def test_add_then_get_round_trips_every_field(action_case: Case) -> None:
    action = make_deal_action(
        later(5),
        actor_user_id=uid("kim"),
        snapshot=make_sync("introduction", "best"),
        action_type="제안",
        action="제안 발표",
        next_action="견적 회신",
        due_date=date(2026, 2, 3),
        memo="내용",
    )
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored.id == action.id
    assert stored.deal_code == action.deal_code
    assert stored.content == action.content
    assert stored.content.due_date == date(2026, 2, 3)
    assert stored.actor_user_id == uid("kim")
    assert stored.snapshot == make_sync("introduction", "best")
    assert stored.acted_at == later(5)
    assert (stored.created_at, stored.updated_at) == (later(5), later(5))


async def test_long_text_round_trips_without_truncation(action_case: Case) -> None:
    action = make_deal_action(action="가" * 5_000, next_action="😀" * 5_000, memo="메모 " * 8_000)
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.action == "가" * 5_000
    assert stored.content.next_action == "😀" * 5_000
    assert stored.content.memo == action.content.memo
    assert len(stored.content.memo) >= 20_000


async def test_add_with_an_existing_id_raises_already_exists(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)

    with pytest.raises(AlreadyExistsError):
        await action_case.repository.add(action)


async def test_get_unknown_action_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(make_deal_action().id)


async def test_add_for_a_missing_deal_raises_deal_not_found(action_case: Case) -> None:
    with pytest.raises(DealNotFoundError):
        await action_case.repository.add(make_deal_action(deal_code=make_deal_code("ZZZZ")))


@pytest.mark.parametrize(
    ("snapshot", "entity"),
    [
        (make_sync(status_key="no_such_status"), "Status 코드"),
        (make_sync(forecast_key="no_such_forecast"), "Forecast 코드"),
    ],
)
async def test_add_with_an_unknown_snapshot_code_raises_invalid_reference(
    action_case: Case, snapshot: object, entity: str
) -> None:
    await action_case.ensure_deal(make_deal_code())
    action = make_deal_action(snapshot=snapshot)
    await action_case.ensure_actor(action)

    with pytest.raises(InvalidReferenceError) as caught:
        await action_case.repository.add(action)

    assert caught.value.entity == entity


async def test_update_persists_the_content_and_updated_at(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)
    action.revise(
        make_action_content(
            action="변경",
            next_action="다음",
            due_date=date(2026, 5, 5),
            memo="c",
            action_type="통화",
        ),
        later(10),
    )
    await attach_catalog_type(action_case.action_types, action)

    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.content == action.content
    assert (stored.content.action, stored.content.next_action) == ("변경", "다음")
    assert stored.content.due_date == date(2026, 5, 5)
    assert stored.content.action_type.name == "통화"
    assert stored.updated_at == later(10)


async def test_update_writes_only_content_and_updated_at(action_case: Case) -> None:
    action = make_deal_action(
        later(5), actor_user_id=uid("kim"), snapshot=make_sync("introduction", "best")
    )
    await action_case.add(action)
    action.revise(
        make_action_content(action="변경", action_type=action.content.action_type), later(10)
    )
    action.actor_user_id = uid("park")  # 도메인이 막는 변경이지만 저장소도 쓰지 않아야 한다
    action.snapshot = make_sync("prospecting", "pipeline")
    action.acted_at = later(99)

    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.content.action == "변경"
    assert stored.actor_user_id == uid("kim")
    assert stored.snapshot == make_sync("introduction", "best")
    assert stored.acted_at == later(5)
    assert stored.created_at == later(5)


async def test_update_unknown_action_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.update(make_deal_action())


async def test_delete_removes_the_row_physically(action_case: Case) -> None:
    action = make_deal_action()
    await action_case.add(action)

    await action_case.repository.delete(action.id)

    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(action.id)
    assert await action_case.search() == []


async def test_delete_unknown_raises_not_found(action_case: Case) -> None:
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.delete(make_deal_action().id)


async def test_deleting_the_deal_deletes_its_actions_and_only_its_own(action_case: Case) -> None:
    mine = make_deal_action(action="내 활동", deal_code=make_deal_code("A001"))
    other = make_deal_action(action="남의 활동", deal_code=make_deal_code("B002"))
    await action_case.add(mine)
    await action_case.add(other)

    await action_case.deals.delete(mine.deal_code)

    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(mine.id)
    assert (await action_case.repository.get(other.id)).id == other.id
    assert await action_case.search(deal_code=other.deal_code) == ["남의 활동"]


async def test_round_trips_type_reference_with_current_name(action_case: Case) -> None:
    action = make_deal_action(action_type="데모")
    await action_case.add(action)

    stored = await action_case.repository.get(action.id)

    assert stored.content.action_type == action.content.action_type
    assert stored.content.action_type.name == "데모"
    assert (await action_case.action_types.get(stored.content.action_type.id)).name == "데모"


async def test_renamed_type_name_is_read_back(action_case: Case) -> None:
    action = make_deal_action(action_type="데모")
    await action_case.add(action)
    renamed = await action_case.action_types.get(action.content.action_type.id)
    renamed.rename("시연", later(5))
    await action_case.action_types.update(renamed)

    by_get = await action_case.repository.get(action.id)
    (by_search,) = await action_case.found()

    assert by_get.content.action_type.name == "시연"
    assert by_search.content.action_type.name == "시연"
    assert by_get.content.action_type.id == action.content.action_type.id


async def test_unknown_type_id_raises_invalid_reference(action_case: Case) -> None:
    await action_case.ensure_deal(make_deal_code())
    action = make_deal_action(action_type=make_type_ref("ZZ 없는 유형"))
    await action_case.ensure_actor(action)

    with pytest.raises(InvalidReferenceError) as caught:
        await action_case.repository.add(action)

    assert caught.value.entity == "Action 유형"


async def test_count_by_action_type(action_case: Case) -> None:
    custom = make_action_type("ZZ 집계")
    await action_case.action_types.add(custom)
    for _ in range(2):
        await action_case.add(make_deal_action(action_type=custom.ref))
    await action_case.add(make_deal_action(action_type="통화"))
    await action_case.add(make_deal_action(action_type="통화"))
    await action_case.add(make_deal_action(action_type="통화"))
    call = next(t for t in await action_case.action_types.list() if t.name == "통화")

    counts = await action_case.repository.count_by_action_type()

    assert counts[custom.id] == 2
    assert counts[call.id] == 3


async def test_count_by_action_type_leaves_out_types_without_actions(action_case: Case) -> None:
    unused = make_action_type("ZZ 미사용")
    await action_case.action_types.add(unused)

    assert unused.id not in await action_case.repository.count_by_action_type()


async def test_update_can_move_an_action_to_another_type(action_case: Case) -> None:
    action = make_deal_action(action_type="통화")
    await action_case.add(action)
    action.revise(make_action_content(action_type="협상"), later(10))
    await attach_catalog_type(action_case.action_types, action)

    await action_case.repository.update(action)

    stored = await action_case.repository.get(action.id)
    assert stored.content.action_type == action.content.action_type
    assert stored.content.action_type.name == "협상"
