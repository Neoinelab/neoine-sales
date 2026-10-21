"""ActionTypeRepository 계약(AC-1·4~6): Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

기본 유형 8개(시드)가 양쪽에 있어 비어 있는 저장소를 가정하지 않는다. 이름은 시드와 겹치지 않는 값을
쓰고, 목록은 `mine`으로 자기가 만든 행만 비교한다.
정렬 계약: 기본 유형 먼저(default_order), 직접 만든 것은 lower(name) 코드 포인트 순, 같으면 id.
"""

from typing import TYPE_CHECKING

import pytest

from app.domain.action_type.errors import (
    ActionTypeInUseError,
    ActionTypeNotFoundError,
    DuplicateActionTypeNameError,
)
from app.domain.action_type.values import ActionTypeId
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES, make_action_type
from tests.support.expect import raises_with
from tests.support.ids import new_id

if TYPE_CHECKING:
    from tests.unit.repositories.action_type_case import ActionTypeCase


async def test_add_then_get_round_trips_a_custom_type_with_its_creator(
    action_type_case: ActionTypeCase,
) -> None:
    creator = UserId(new_id())
    await action_type_case.ensure_user(creator)
    action_type = make_action_type("ZZ 웨비나", created_by=creator, now=NOW)
    await action_type_case.types.add(action_type)

    stored = await action_type_case.types.get(action_type.id)

    assert stored.id == action_type.id
    assert stored.name == "ZZ 웨비나"
    assert (stored.is_default, stored.default_order) == (False, None)
    assert stored.created_by_user_id == creator
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)
    assert stored.ref == action_type.ref


async def test_a_default_type_round_trips_without_a_creator(
    action_type_case: ActionTypeCase,
) -> None:
    action_type = make_action_type("ZZ 기본", is_default=True, default_order=99)
    await action_type_case.types.add(action_type)

    stored = await action_type_case.types.get(action_type.id)

    assert (stored.is_default, stored.default_order, stored.created_by_user_id) == (True, 99, None)


async def test_get_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(ActionTypeId(new_id()))


async def test_the_seeded_defaults_are_listed_first_in_default_order(
    action_type_case: ActionTypeCase,
) -> None:
    await action_type_case.types.add(make_action_type("ZZ 직접"))

    listed = await action_type_case.types.list()

    assert [t.name for t in listed[:8]] == list(DEFAULT_ACTION_TYPE_NAMES)
    assert all(t.is_default for t in listed[:8])
    assert not any(t.is_default for t in listed[8:])


async def test_list_puts_defaults_by_default_order_before_custom_types_by_name(
    action_type_case: ActionTypeCase,
) -> None:
    custom_b = make_action_type("ZZ beta")
    custom_a = make_action_type("ZZ Alpha")
    default_2 = make_action_type("ZZ 기본2", is_default=True, default_order=902)
    default_1 = make_action_type("ZZ 기본1", is_default=True, default_order=901)
    for item in (custom_b, default_2, custom_a, default_1):
        await action_type_case.types.add(item)

    listed = await action_type_case.mine({custom_b.id, custom_a.id, default_2.id, default_1.id})

    assert [t.id for t in listed] == [default_1.id, default_2.id, custom_a.id, custom_b.id]


async def test_list_sorts_custom_types_by_lower_name_in_code_point_order(
    action_type_case: ActionTypeCase,
) -> None:
    korean = make_action_type("ZZ 나")
    upper = make_action_type("ZZ Z")
    lower = make_action_type("zz a")
    for item in (korean, upper, lower):
        await action_type_case.types.add(item)

    listed = await action_type_case.mine({korean.id, upper.id, lower.id})

    assert [t.id for t in listed] == [lower.id, upper.id, korean.id]


async def test_list_for_update_returns_the_same_rows(action_type_case: ActionTypeCase) -> None:
    await action_type_case.types.add(make_action_type("ZZ 잠금"))

    plain = await action_type_case.types.list()
    locked = await action_type_case.types.list(for_update=True)

    assert [t.id for t in locked] == [t.id for t in plain]


@pytest.mark.parametrize("duplicate", ["zz label", "ZZ LABEL", "Zz Label"])
async def test_add_with_the_same_name_ignoring_case_conflicts(
    action_type_case: ActionTypeCase, duplicate: str
) -> None:
    await action_type_case.types.add(make_action_type("ZZ Label"))

    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await action_type_case.types.add(make_action_type(duplicate))


async def test_add_with_the_name_of_a_seeded_default_conflicts(
    action_type_case: ActionTypeCase,
) -> None:
    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.add(make_action_type("미팅"))


async def test_add_with_an_existing_id_raises_already_exists(
    action_type_case: ActionTypeCase,
) -> None:
    first = make_action_type("ZZ One")
    await action_type_case.types.add(first)

    with pytest.raises(AlreadyExistsError):
        await action_type_case.types.add(make_action_type("ZZ Two", entity_id=first.id))


async def test_add_with_an_unknown_creator_raises_invalid_reference(
    action_type_case: ActionTypeCase,
) -> None:
    with pytest.raises(InvalidReferenceError) as caught:
        await action_type_case.types.add(make_action_type("ZZ 유령", created_by=UserId(new_id())))

    assert caught.value.entity == "사용자"


async def test_the_repository_stays_usable_after_a_conflict(
    action_type_case: ActionTypeCase,
) -> None:
    await action_type_case.types.add(make_action_type("ZZ One"))
    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.add(make_action_type("zz one"))
    after = make_action_type("ZZ Two")

    await action_type_case.types.add(after)

    assert (await action_type_case.types.get(after.id)).name == "ZZ Two"


async def test_update_persists_the_new_name_and_updated_at(
    action_type_case: ActionTypeCase,
) -> None:
    action_type = make_action_type("ZZ Old")
    await action_type_case.types.add(action_type)
    action_type.rename("ZZ New", later(60))

    await action_type_case.types.update(action_type)

    stored = await action_type_case.types.get(action_type.id)
    assert (stored.name, stored.updated_at, stored.created_at) == ("ZZ New", later(60), NOW)


async def test_update_keeps_the_default_flag_and_order(action_type_case: ActionTypeCase) -> None:
    action_type = make_action_type("ZZ 기본", is_default=True, default_order=903)
    await action_type_case.types.add(action_type)
    action_type.rename("ZZ 기본 바뀜", later(60))

    await action_type_case.types.update(action_type)

    stored = await action_type_case.types.get(action_type.id)
    assert (stored.is_default, stored.default_order) == (True, 903)


async def test_update_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.update(make_action_type("ZZ 유령"))


async def test_update_to_another_types_name_ignoring_case_conflicts(
    action_type_case: ActionTypeCase,
) -> None:
    await action_type_case.types.add(make_action_type("ZZ One"))
    other = make_action_type("ZZ Two")
    await action_type_case.types.add(other)
    other.rename("zz one", later(60))

    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(
    action_type_case: ActionTypeCase,
) -> None:
    action_type = make_action_type("ZZ Name")
    await action_type_case.types.add(action_type)
    action_type.rename("zz name", later(60))

    await action_type_case.types.update(action_type)

    assert (await action_type_case.types.get(action_type.id)).name == "zz name"


async def test_delete_removes_only_that_type(action_type_case: ActionTypeCase) -> None:
    gone = make_action_type("ZZ Gone")
    kept = make_action_type("ZZ Kept")
    await action_type_case.types.add(gone)
    await action_type_case.types.add(kept)

    await action_type_case.types.delete(gone.id)

    assert [t.id for t in await action_type_case.mine({gone.id, kept.id})] == [kept.id]
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(gone.id)


async def test_a_deleted_name_can_be_added_again(action_type_case: ActionTypeCase) -> None:
    first = make_action_type("ZZ Again")
    await action_type_case.types.add(first)
    await action_type_case.types.delete(first.id)
    again = make_action_type("ZZ Again")

    await action_type_case.types.add(again)

    assert (await action_type_case.types.get(again.id)).id == again.id


async def test_delete_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.delete(ActionTypeId(new_id()))


async def test_delete_a_type_used_by_actions_reports_the_real_count_and_keeps_the_row(
    action_type_case: ActionTypeCase,
) -> None:
    used = make_action_type("ZZ Used")
    await action_type_case.types.add(used)
    await action_type_case.use(used, count=3)

    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        await action_type_case.types.delete(used.id)

    assert (await action_type_case.types.get(used.id)).name == "ZZ Used"


async def test_delete_a_seeded_default_type_used_by_actions_is_refused(
    action_type_case: ActionTypeCase,
) -> None:
    meeting = next(t for t in await action_type_case.types.list() if t.name == "미팅")
    await action_type_case.use(meeting, count=2)

    with pytest.raises(ActionTypeInUseError) as caught:
        await action_type_case.types.delete(meeting.id)

    assert caught.value.usage == 2


async def test_a_type_is_deletable_after_its_actions_are_deleted(
    action_type_case: ActionTypeCase,
) -> None:
    used = make_action_type("ZZ Used")
    await action_type_case.types.add(used)
    (action,) = await action_type_case.use(used)
    await action_type_case.actions.delete(action.id)

    await action_type_case.types.delete(used.id)

    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(used.id)
