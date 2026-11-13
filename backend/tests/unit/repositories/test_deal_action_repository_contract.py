"""DealActionRepository 계약(저장·수정·삭제·참조): Fake와 SQL(PostgreSQL)에 같은 테스트."""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.errors import DealActionNotFoundError
from tests.factories import (
    date_after,
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
    """Action을 저장하고 읽으면 모든 필드가 그대로 돌아온다."""
    # given: 모든 필드를 채운 Action
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
    # when: 저장한다
    await action_case.add(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)

    # then: 모든 필드가 저장한 값과 같다
    assert stored.id == action.id
    assert stored.deal_code == action.deal_code
    assert stored.content == action.content
    assert stored.content.due_date == date(2026, 2, 3)
    assert stored.actor_user_id == uid("kim")
    assert stored.snapshot == make_sync("introduction", "best")
    assert stored.acted_on == date_after(0)
    assert (stored.created_at, stored.updated_at) == (later(5), later(5))


async def test_long_text_round_trips_without_truncation(action_case: Case) -> None:
    """긴 텍스트는 잘리지 않고 저장된다."""
    # given: 5,000자 이상의 진행사항·Next Action과 20,000자 이상의 Memo를 가진 Action
    action = make_deal_action(action="가" * 5_000, next_action="😀" * 5_000, memo="메모 " * 8_000)
    # when: 저장한다
    await action_case.add(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)

    # then: 어느 필드도 잘리지 않는다
    assert stored.content.action == "가" * 5_000
    assert stored.content.next_action == "😀" * 5_000
    assert stored.content.memo == action.content.memo
    assert len(stored.content.memo) >= 20_000


async def test_add_with_an_existing_id_raises_already_exists(action_case: Case) -> None:
    """같은 id의 Action을 다시 저장하면 이미 존재 오류가 난다."""
    # given: 이미 저장된 Action
    action = make_deal_action()
    await action_case.add(action)

    # when·then: 같은 id로 다시 저장하면 이미 존재 오류가 난다
    with pytest.raises(AlreadyExistsError):
        await action_case.repository.add(action)


async def test_get_unknown_action_raises_not_found(action_case: Case) -> None:
    """없는 Action을 읽으면 찾을 수 없음 오류가 난다."""
    # when·then: 없는 id를 읽으면 Action 없음 오류가 난다
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(make_deal_action().id)


async def test_add_for_a_missing_deal_raises_deal_not_found(action_case: Case) -> None:
    """없는 Deal에 Action을 저장하면 Deal 없음 오류가 난다."""
    # when·then: 저장소에 없는 Deal 코드의 Action을 저장하면 Deal 없음 오류가 난다
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
    """없는 Status·Forecast 코드의 스냅숏으로 저장하면 잘못된 참조 오류가 난다."""
    # given: Deal·수행자·유형은 있고 스냅숏 코드만 없는 Action
    await action_case.ensure_deal(make_deal_code())
    action = make_deal_action(snapshot=snapshot)
    await action_case.ensure_actor(action)
    await attach_catalog_type(action_case.action_types, action)

    # when: 저장한다
    with pytest.raises(InvalidReferenceError) as caught:
        await action_case.repository.add(action)

    # then: 오류가 해당 코드 종류를 가리킨다
    assert caught.value.entity == entity


async def test_update_persists_the_content_and_updated_at(action_case: Case) -> None:
    """수정하면 내용과 수정 시각이 저장된다."""
    # given: 저장된 Action을 내용·유형까지 고친 상태
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

    # when: 수정을 저장한다
    await action_case.repository.update(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 고친 내용과 수정 시각이 읽힌다
    assert stored.content == action.content
    assert (stored.content.action, stored.content.next_action) == ("변경", "다음")
    assert stored.content.due_date == date(2026, 5, 5)
    assert stored.content.action_type.name == "통화"
    assert stored.updated_at == later(10)


async def test_update_does_not_write_the_actor_or_the_snapshot(action_case: Case) -> None:
    """수정은 수행자·스냅숏·생성 시각을 쓰지 않는다(수행일은 따로 저장한다)."""
    # given: 저장된 Action에서 내용과 함께 수행자·스냅숏도 메모리에서 바꾼 상태
    action = make_deal_action(
        later(5), actor_user_id=uid("kim"), snapshot=make_sync("introduction", "best")
    )
    await action_case.add(action)
    action.revise(
        make_action_content(action="변경", action_type=action.content.action_type), later(10)
    )
    action.actor_user_id = uid("park")  # 도메인이 막는 변경이지만 저장소도 쓰지 않아야 한다
    action.snapshot = make_sync("prospecting", "pipeline")

    # when: 수정을 저장한다
    await action_case.repository.update(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 내용만 바뀌고 수행자·스냅숏·수행일·생성 시각은 그대로다
    assert stored.content.action == "변경"
    assert stored.actor_user_id == uid("kim")
    assert stored.snapshot == make_sync("introduction", "best")
    assert stored.acted_on == date_after(0)
    assert stored.created_at == later(5)


async def test_update_persists_the_acted_on(action_case: Case) -> None:
    """수정하면 수행일(date)도 저장되고 다른 날짜 값은 바뀌지 않는다.

    테스트 코드: AC-127
    """
    # given: 저장된 Action에 수행일만 메모리에서 바꾼 상태
    action = make_deal_action(later(5))
    await action_case.add(action)
    action.acted_on = date_after(-3)
    action.updated_at = later(10)

    # when: 수정을 저장한다
    await action_case.repository.update(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 새 수행일과 수정 시각이 읽히고 내용·생성 시각은 그대로다
    assert stored.acted_on == date_after(-3)
    assert stored.updated_at == later(10)
    assert stored.content == action.content
    assert stored.created_at == later(5)
    # then: 검색 결과(수행일 순서의 읽기)에도 새 수행일이 보인다
    assert [found.acted_on for found in await action_case.found()] == [date_after(-3)]


async def test_update_unknown_action_raises_not_found(action_case: Case) -> None:
    """없는 Action을 수정하면 찾을 수 없음 오류가 난다."""
    # when·then: 저장된 적 없는 Action을 수정하면 Action 없음 오류가 난다
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.update(make_deal_action())


async def test_delete_removes_the_row_physically(action_case: Case) -> None:
    """삭제하면 행이 실제로 사라진다."""
    # given: 저장된 Action
    action = make_deal_action()
    await action_case.add(action)

    # when: 삭제한다
    await action_case.repository.delete(action.id)

    # then: 읽기는 Action 없음 오류가 나고
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(action.id)
    # then: 검색에도 나오지 않는다
    assert await action_case.search() == []


async def test_delete_unknown_raises_not_found(action_case: Case) -> None:
    """없는 Action을 삭제하면 찾을 수 없음 오류가 난다."""
    # when·then: 없는 id를 삭제하면 Action 없음 오류가 난다
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.delete(make_deal_action().id)


async def test_deleting_the_deal_deletes_its_actions_and_only_its_own(action_case: Case) -> None:
    """Deal을 삭제하면 그 Deal의 Action만 함께 삭제된다."""
    # given: 서로 다른 두 Deal의 Action
    mine = make_deal_action(action="내 활동", deal_code=make_deal_code("A001"))
    other = make_deal_action(action="남의 활동", deal_code=make_deal_code("B002"))
    await action_case.add(mine)
    await action_case.add(other)

    # when: 한 Deal을 삭제한다
    await action_case.deals.delete(mine.deal_code)

    # then: 그 Deal의 Action은 사라지고
    with pytest.raises(DealActionNotFoundError):
        await action_case.repository.get(mine.id)
    # then: 다른 Deal의 Action은 그대로다
    assert (await action_case.repository.get(other.id)).id == other.id
    assert await action_case.search(deal_code=other.deal_code) == ["남의 활동"]


async def test_round_trips_type_reference_with_current_name(action_case: Case) -> None:
    """Action을 읽으면 유형 참조와 현재 이름이 함께 돌아온다."""
    # given: 유형 "데모"의 Action을 저장한 상태
    action = make_deal_action(action_type="데모")
    await action_case.add(action)

    # when: 읽는다
    stored = await action_case.repository.get(action.id)

    # then: 유형 참조와 현재 이름이 맞다
    assert stored.content.action_type == action.content.action_type
    assert stored.content.action_type.name == "데모"
    assert (await action_case.action_types.get(stored.content.action_type.id)).name == "데모"


async def test_renamed_type_name_is_read_back(action_case: Case) -> None:
    """유형 이름을 바꾸면 읽기와 검색 모두 새 이름을 돌려준다."""
    # given: 유형 "데모"의 Action과 그 유형을 "시연"으로 바꾼 상태
    action = make_deal_action(action_type="데모")
    await action_case.add(action)
    renamed = await action_case.action_types.get(action.content.action_type.id)
    renamed.rename("시연", later(5))
    await action_case.action_types.update(renamed)

    # when: 읽기와 검색으로 조회한다
    by_get = await action_case.repository.get(action.id)
    (by_search,) = await action_case.found()

    # then: 둘 다 새 이름이고 유형 id는 그대로다
    assert by_get.content.action_type.name == "시연"
    assert by_search.content.action_type.name == "시연"
    assert by_get.content.action_type.id == action.content.action_type.id


async def test_unknown_type_id_raises_invalid_reference(action_case: Case) -> None:
    """없는 유형 id로 저장하면 잘못된 참조 오류가 난다."""
    # given: Deal·수행자는 있고 유형 id만 없는 Action
    await action_case.ensure_deal(make_deal_code())
    action = make_deal_action(action_type=make_type_ref("ZZ 없는 유형"))
    await action_case.ensure_actor(action)

    # when: 저장한다
    with pytest.raises(InvalidReferenceError) as caught:
        await action_case.repository.add(action)

    # then: 오류가 Action 유형을 가리킨다
    assert caught.value.entity == "Action 유형"


async def test_count_by_action_type(action_case: Case) -> None:
    """유형별 Action 수를 센다."""
    # given: 새 유형 Action 2건과 "통화" Action 3건
    custom = make_action_type("ZZ 집계")
    await action_case.action_types.add(custom)
    for _ in range(2):
        await action_case.add(make_deal_action(action_type=custom.ref))
    await action_case.add(make_deal_action(action_type="통화"))
    await action_case.add(make_deal_action(action_type="통화"))
    await action_case.add(make_deal_action(action_type="통화"))
    call = next(t for t in await action_case.action_types.list() if t.name == "통화")

    # when: 유형별 개수를 센다
    counts = await action_case.repository.count_by_action_type()

    # then: 유형마다 자기 Action 수가 나온다
    assert counts[custom.id] == 2
    assert counts[call.id] == 3


async def test_count_by_action_type_leaves_out_types_without_actions(action_case: Case) -> None:
    """Action이 없는 유형은 개수 결과에 나오지 않는다."""
    # given: Action이 하나도 없는 유형
    unused = make_action_type("ZZ 미사용")
    await action_case.action_types.add(unused)

    # when: 유형별 개수를 센다
    counts = await action_case.repository.count_by_action_type()
    # then: 그 유형은 결과에 없다
    assert unused.id not in counts


async def test_update_can_move_an_action_to_another_type(action_case: Case) -> None:
    """수정으로 Action의 유형을 다른 유형으로 옮길 수 있다."""
    # given: "통화" 유형의 Action을 "협상" 유형으로 고친 상태
    action = make_deal_action(action_type="통화")
    await action_case.add(action)
    action.revise(make_action_content(action_type="협상"), later(10))
    await attach_catalog_type(action_case.action_types, action)

    # when: 수정을 저장한다
    await action_case.repository.update(action)

    # when: 다시 읽는다
    stored = await action_case.repository.get(action.id)
    # then: 유형이 "협상"으로 바뀌어 있다
    assert stored.content.action_type == action.content.action_type
    assert stored.content.action_type.name == "협상"
