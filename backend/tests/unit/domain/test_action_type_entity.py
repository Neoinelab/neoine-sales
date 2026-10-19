"""ActionType 엔티티(AC-2·5·6·10): 생성자 기록, 이름 변경, 사용 중 삭제 거부, 오류 종류와 문구."""

from uuid import uuid4

import pytest
from app.domain.action_type.entities import ActionType
from app.domain.action_type.errors import (
    ActionTypeInUseError,
    ActionTypeNotFoundError,
    DuplicateActionTypeNameError,
    UnknownActionTypeError,
)
from app.domain.action_type.values import ActionTypeId, ActionTypeRef

from app.domain.common.errors import (
    AlreadyExistsError,
    InvalidStateError,
    InvalidValueError,
    NotFoundError,
)
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_action_type import make_action_type
from tests.support.expect import raises_with

CREATOR = UserId(uuid4())


def test_create_sets_creator_and_is_not_default() -> None:
    action_type = ActionType.create(name="웨비나", created_by=CREATOR, now=NOW)

    assert action_type.name == "웨비나"
    assert action_type.is_default is False
    assert action_type.default_order is None
    assert action_type.created_by_user_id == CREATOR
    assert action_type.created_at == action_type.updated_at == NOW


def test_create_generates_a_new_id_each_time() -> None:
    first = ActionType.create(name="웨비나", created_by=CREATOR, now=NOW)
    second = ActionType.create(name="웨비나", created_by=CREATOR, now=NOW)

    assert first.id != second.id


def test_rename_changes_the_name_and_touches_updated_at() -> None:
    action_type = make_action_type("미팅", is_default=True, default_order=2)

    action_type.rename("회의", later(60))

    assert action_type.name == "회의"
    assert (action_type.is_default, action_type.default_order) == (True, 2)
    assert action_type.created_at == NOW
    assert action_type.updated_at == later(60)


def test_ref_carries_the_id_and_the_current_name() -> None:
    action_type = make_action_type("웨비나")

    assert action_type.ref == ActionTypeRef(action_type.id, "웨비나")

    action_type.rename("세미나", later(5))

    assert action_type.ref.name == "세미나"


def test_used_action_type_cannot_be_deleted_and_the_message_has_the_count() -> None:
    action_type = make_action_type()

    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        action_type.ensure_deletable(3)


def test_in_use_error_keeps_the_usage_count() -> None:
    with pytest.raises(ActionTypeInUseError) as raised:
        make_action_type().ensure_deletable(2)

    assert raised.value.usage == 2


def test_unused_action_type_is_deletable_even_when_it_is_a_default() -> None:
    make_action_type("기타", is_default=True, default_order=8).ensure_deletable(0)


def test_action_type_errors_map_to_not_found_conflict_invalid_state_and_invalid_value() -> None:
    assert issubclass(ActionTypeNotFoundError, NotFoundError)
    assert issubclass(DuplicateActionTypeNameError, AlreadyExistsError)
    assert issubclass(ActionTypeInUseError, InvalidStateError)
    assert issubclass(UnknownActionTypeError, InvalidValueError)


def test_error_messages_are_the_user_text() -> None:
    assert str(DuplicateActionTypeNameError("데모")) == "이미 있는 유형 이름입니다."
    assert str(UnknownActionTypeError()) == "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
    assert str(ActionTypeNotFoundError(uuid4())).startswith("Action 유형")


def test_not_found_error_keeps_the_identifier() -> None:
    type_id = ActionTypeId(uuid4())

    assert ActionTypeNotFoundError(type_id).identifier == type_id
