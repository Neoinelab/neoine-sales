"""ActionTypeRepository 계약: Fake와 SQL 구현(실제 PostgreSQL)에 같은 테스트를 적용한다.

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
    """직접 만든 유형을 저장하고 읽으면 생성자와 시각까지 같다."""
    # given: 생성자 사용자
    creator = UserId(new_id())
    await action_type_case.ensure_user(creator)
    action_type = make_action_type("ZZ 웨비나", created_by=creator, now=NOW)

    # when: 저장하고 읽는다
    await action_type_case.types.add(action_type)
    stored = await action_type_case.types.get(action_type.id)

    # then: 저장한 값 그대로 읽힌다
    assert stored.id == action_type.id
    assert stored.name == "ZZ 웨비나"
    assert (stored.is_default, stored.default_order) == (False, None)
    assert stored.created_by_user_id == creator
    assert (stored.created_at, stored.updated_at) == (NOW, NOW)
    assert stored.ref == action_type.ref


async def test_a_default_type_round_trips_without_a_creator(
    action_type_case: ActionTypeCase,
) -> None:
    """기본 유형은 생성자 없이 저장하고 읽는다."""
    # given: 생성자가 없는 기본 유형
    action_type = make_action_type("ZZ 기본", is_default=True, default_order=99)

    # when: 저장하고 읽는다
    await action_type_case.types.add(action_type)
    stored = await action_type_case.types.get(action_type.id)

    # then: 기본 여부·순서가 유지되고 생성자는 없다
    assert (stored.is_default, stored.default_order, stored.created_by_user_id) == (True, 99, None)


async def test_get_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    """없는 유형을 읽으면 없음 오류다."""
    # when·then: 없는 id로 읽으면 없음 오류다
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(ActionTypeId(new_id()))


async def test_the_seeded_defaults_are_listed_first_in_default_order(
    action_type_case: ActionTypeCase,
) -> None:
    """시드 기본 유형 8개가 기본 순서대로 맨 앞에 나온다."""
    # given: 직접 만든 유형 하나
    await action_type_case.types.add(make_action_type("ZZ 직접"))

    # when: 목록을 읽는다
    listed = await action_type_case.types.list()

    # then: 앞 8개는 기본 유형이고 나머지는 직접 만든 것이다
    assert [t.name for t in listed[:8]] == list(DEFAULT_ACTION_TYPE_NAMES)
    assert all(t.is_default for t in listed[:8])
    assert not any(t.is_default for t in listed[8:])


async def test_list_puts_defaults_by_default_order_before_custom_types_by_name(
    action_type_case: ActionTypeCase,
) -> None:
    """기본 유형은 기본 순서대로, 직접 만든 유형은 이름 순으로 그 뒤에 나온다."""
    # given: 기본 유형 둘과 직접 만든 유형 둘을 섞어 저장한다
    custom_b = make_action_type("ZZ beta")
    custom_a = make_action_type("ZZ Alpha")
    default_2 = make_action_type("ZZ 기본2", is_default=True, default_order=902)
    default_1 = make_action_type("ZZ 기본1", is_default=True, default_order=901)
    for item in (custom_b, default_2, custom_a, default_1):
        await action_type_case.types.add(item)

    # when: 목록을 읽는다
    listed = await action_type_case.mine({custom_b.id, custom_a.id, default_2.id, default_1.id})

    # then: 기본 순서 → 이름 순이다
    assert [t.id for t in listed] == [default_1.id, default_2.id, custom_a.id, custom_b.id]


async def test_list_sorts_custom_types_by_lower_name_in_code_point_order(
    action_type_case: ActionTypeCase,
) -> None:
    """직접 만든 유형은 소문자 이름의 코드 포인트 순으로 나온다."""
    # given: 한글·대문자·소문자 이름의 유형
    korean = make_action_type("ZZ 나")
    upper = make_action_type("ZZ Z")
    lower = make_action_type("zz a")
    for item in (korean, upper, lower):
        await action_type_case.types.add(item)

    # when: 목록을 읽는다
    listed = await action_type_case.mine({korean.id, upper.id, lower.id})

    # then: 소문자 이름의 코드 포인트 순이다
    assert [t.id for t in listed] == [lower.id, upper.id, korean.id]


async def test_list_for_update_returns_the_same_rows(action_type_case: ActionTypeCase) -> None:
    """잠금 조회도 같은 행을 같은 순서로 돌려준다."""
    # given: 유형 하나
    await action_type_case.types.add(make_action_type("ZZ 잠금"))

    # when: 일반 조회와 잠금 조회를 한다
    plain = await action_type_case.types.list()
    locked = await action_type_case.types.list(for_update=True)

    # then: 두 결과가 같다
    assert [t.id for t in locked] == [t.id for t in plain]


@pytest.mark.parametrize("duplicate", ["zz label", "ZZ LABEL", "Zz Label"])
async def test_add_with_the_same_name_ignoring_case_conflicts(
    action_type_case: ActionTypeCase, duplicate: str
) -> None:
    """대소문자만 다른 같은 이름으로 추가하면 중복 오류다."""
    # given: "ZZ Label" 유형
    await action_type_case.types.add(make_action_type("ZZ Label"))

    # when·then: 대소문자만 다른 이름을 추가하면 중복 오류다
    with raises_with(DuplicateActionTypeNameError, "이미 있는 유형 이름입니다."):
        await action_type_case.types.add(make_action_type(duplicate))


async def test_add_with_the_name_of_a_seeded_default_conflicts(
    action_type_case: ActionTypeCase,
) -> None:
    """시드 기본 유형과 같은 이름은 중복이다."""
    # when·then: "미팅"을 추가하면 중복 오류다
    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.add(make_action_type("미팅"))


async def test_add_with_an_existing_id_raises_already_exists(
    action_type_case: ActionTypeCase,
) -> None:
    """이미 있는 id로 추가하면 이미 있음 오류다."""
    # given: 저장된 유형
    first = make_action_type("ZZ One")
    await action_type_case.types.add(first)

    # when·then: 같은 id에 다른 이름으로 추가하면 이미 있음 오류다
    with pytest.raises(AlreadyExistsError):
        await action_type_case.types.add(make_action_type("ZZ Two", entity_id=first.id))


async def test_add_with_an_unknown_creator_raises_invalid_reference(
    action_type_case: ActionTypeCase,
) -> None:
    """없는 사용자가 만든 것으로 추가하면 잘못된 참조 오류다."""
    # when: 없는 사용자를 생성자로 추가한다
    with pytest.raises(InvalidReferenceError) as caught:
        await action_type_case.types.add(make_action_type("ZZ 유령", created_by=UserId(new_id())))

    # then: 오류가 사용자를 가리킨다
    assert caught.value.entity == "사용자"


async def test_the_repository_stays_usable_after_a_conflict(
    action_type_case: ActionTypeCase,
) -> None:
    """중복 오류 뒤에도 저장소를 계속 쓸 수 있다."""
    # given: 중복 오류가 한 번 난 저장소
    await action_type_case.types.add(make_action_type("ZZ One"))
    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.add(make_action_type("zz one"))
    after = make_action_type("ZZ Two")

    # when: 다른 유형을 추가한다
    await action_type_case.types.add(after)

    # then: 저장되어 읽힌다
    assert (await action_type_case.types.get(after.id)).name == "ZZ Two"


async def test_update_persists_the_new_name_and_updated_at(
    action_type_case: ActionTypeCase,
) -> None:
    """수정하면 새 이름과 수정 시각이 저장된다."""
    # given: 저장된 유형의 이름을 바꿔 둔다
    action_type = make_action_type("ZZ Old")
    await action_type_case.types.add(action_type)
    action_type.rename("ZZ New", later(60))

    # when: 수정을 저장한다
    await action_type_case.types.update(action_type)

    # then: 새 이름·수정 시각이 읽히고 생성 시각은 그대로다
    stored = await action_type_case.types.get(action_type.id)
    assert (stored.name, stored.updated_at, stored.created_at) == ("ZZ New", later(60), NOW)


async def test_update_keeps_the_default_flag_and_order(action_type_case: ActionTypeCase) -> None:
    """수정해도 기본 여부와 순서는 유지된다."""
    # given: 저장된 기본 유형의 이름을 바꿔 둔다
    action_type = make_action_type("ZZ 기본", is_default=True, default_order=903)
    await action_type_case.types.add(action_type)
    action_type.rename("ZZ 기본 바뀜", later(60))

    # when: 수정을 저장한다
    await action_type_case.types.update(action_type)

    # then: 기본 여부·순서가 그대로다
    stored = await action_type_case.types.get(action_type.id)
    assert (stored.is_default, stored.default_order) == (True, 903)


async def test_update_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    """없는 유형을 수정하면 없음 오류다."""
    # when·then: 저장하지 않은 유형을 수정하면 없음 오류다
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.update(make_action_type("ZZ 유령"))


async def test_update_to_another_types_name_ignoring_case_conflicts(
    action_type_case: ActionTypeCase,
) -> None:
    """다른 유형의 이름과 대소문자만 다르게 바꾸면 중복 오류다."""
    # given: 유형 둘이 있고 둘째를 첫째와 대소문자만 다른 이름으로 바꿔 둔다
    await action_type_case.types.add(make_action_type("ZZ One"))
    other = make_action_type("ZZ Two")
    await action_type_case.types.add(other)
    other.rename("zz one", later(60))

    # when·then: 수정을 저장하면 중복 오류다
    with pytest.raises(DuplicateActionTypeNameError):
        await action_type_case.types.update(other)


async def test_update_to_own_name_in_another_case_is_allowed(
    action_type_case: ActionTypeCase,
) -> None:
    """자기 이름의 대소문자만 바꾸는 수정은 허용된다."""
    # given: 저장된 유형의 이름을 대소문자만 바꿔 둔다
    action_type = make_action_type("ZZ Name")
    await action_type_case.types.add(action_type)
    action_type.rename("zz name", later(60))

    # when: 수정을 저장한다
    await action_type_case.types.update(action_type)

    # then: 새 표기로 읽힌다
    assert (await action_type_case.types.get(action_type.id)).name == "zz name"


async def test_delete_removes_only_that_type(action_type_case: ActionTypeCase) -> None:
    """삭제는 그 유형만 지운다."""
    # given: 유형 둘
    gone = make_action_type("ZZ Gone")
    kept = make_action_type("ZZ Kept")
    await action_type_case.types.add(gone)
    await action_type_case.types.add(kept)

    # when: 하나를 삭제한다
    await action_type_case.types.delete(gone.id)

    # then: 다른 하나만 남고 지운 것은 읽히지 않는다
    assert [t.id for t in await action_type_case.mine({gone.id, kept.id})] == [kept.id]
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(gone.id)


async def test_a_deleted_name_can_be_added_again(action_type_case: ActionTypeCase) -> None:
    """지운 이름은 다시 추가할 수 있다."""
    # given: 추가했다가 삭제한 "ZZ Again"
    first = make_action_type("ZZ Again")
    await action_type_case.types.add(first)
    await action_type_case.types.delete(first.id)
    again = make_action_type("ZZ Again")

    # when: 같은 이름으로 다시 추가한다
    await action_type_case.types.add(again)

    # then: 읽힌다
    assert (await action_type_case.types.get(again.id)).id == again.id


async def test_delete_a_missing_type_raises_not_found(action_type_case: ActionTypeCase) -> None:
    """없는 유형을 삭제하면 없음 오류다."""
    # when·then: 없는 id를 삭제하면 없음 오류다
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.delete(ActionTypeId(new_id()))


async def test_delete_a_type_used_by_actions_reports_the_real_count_and_keeps_the_row(
    action_type_case: ActionTypeCase,
) -> None:
    """Action 3건이 쓰는 유형은 실제 건수로 삭제가 거부되고 행은 남는다."""
    # given: Action 3건이 쓰는 유형
    used = make_action_type("ZZ Used")
    await action_type_case.types.add(used)
    await action_type_case.use(used, count=3)

    # when·then: 삭제하면 건수가 담긴 사용 중 오류다
    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        await action_type_case.types.delete(used.id)

    # then: 행은 남아 있다
    assert (await action_type_case.types.get(used.id)).name == "ZZ Used"


async def test_delete_a_seeded_default_type_used_by_actions_is_refused(
    action_type_case: ActionTypeCase,
) -> None:
    """Action이 쓰는 시드 기본 유형도 삭제가 거부된다."""
    # given: Action 2건이 쓰는 시드 유형 "미팅"
    meeting = next(t for t in await action_type_case.types.list() if t.name == "미팅")
    await action_type_case.use(meeting, count=2)

    # when: 삭제한다
    with pytest.raises(ActionTypeInUseError) as caught:
        await action_type_case.types.delete(meeting.id)

    # then: 오류가 사용 건수 2를 가진다
    assert caught.value.usage == 2


async def test_a_type_is_deletable_after_its_actions_are_deleted(
    action_type_case: ActionTypeCase,
) -> None:
    """쓰던 Action을 지우면 유형을 삭제할 수 있다."""
    # given: Action 하나가 쓰던 유형이고 그 Action을 지웠다
    used = make_action_type("ZZ Used")
    await action_type_case.types.add(used)
    (action,) = await action_type_case.use(used)
    await action_type_case.actions.delete(action.id)

    # when: 유형을 삭제한다
    await action_type_case.types.delete(used.id)

    # then: 유형이 더 읽히지 않는다
    with pytest.raises(ActionTypeNotFoundError):
        await action_type_case.types.get(used.id)
