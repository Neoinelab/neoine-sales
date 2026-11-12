"""ActionType 엔티티: 생성자 기록, 이름 변경, 사용 중 삭제 거부, 오류 종류와 문구."""

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
from tests.support.ids import new_id

CREATOR = UserId(new_id())


def test_create_sets_creator_and_is_not_default() -> None:
    """새 유형은 생성자와 생성 시각을 기록하고 기본 유형이 아니다."""
    # when: 사용자가 유형을 만든다
    action_type = ActionType.create(
        entity_id=ActionTypeId(new_id()), name="웨비나", created_by=CREATOR, now=NOW
    )

    # then: 생성자·시각이 기록되고 기본 유형이 아니다
    assert action_type.name == "웨비나"
    assert action_type.is_default is False
    assert action_type.default_order is None
    assert action_type.created_by_user_id == CREATOR
    assert action_type.created_at == action_type.updated_at == NOW


def test_create_uses_the_given_id() -> None:
    """유형은 받은 id를 그대로 가진다."""
    # when: id 12로 유형을 만든다
    action_type = ActionType.create(
        entity_id=ActionTypeId(12), name="웨비나", created_by=CREATOR, now=NOW
    )

    # then: id가 12다
    assert action_type.id == 12


def test_rename_changes_the_name_and_touches_updated_at() -> None:
    """이름을 바꾸면 이름과 수정 시각만 바뀐다."""
    # given: 기본 유형 "미팅"
    action_type = make_action_type("미팅", is_default=True, default_order=2)

    # when: 이름을 "회의"로 바꾼다
    action_type.rename("회의", later(60))

    # then: 이름·수정 시각만 바뀌고 기본 여부·순서·생성 시각은 그대로다
    assert action_type.name == "회의"
    assert (action_type.is_default, action_type.default_order) == (True, 2)
    assert action_type.created_at == NOW
    assert action_type.updated_at == later(60)


def test_ref_carries_the_id_and_the_current_name() -> None:
    """참조는 id와 현재 이름을 담는다."""
    # given: "웨비나" 유형
    action_type = make_action_type("웨비나")

    # when·then: 참조는 id와 이름을 담는다
    assert action_type.ref == ActionTypeRef(action_type.id, "웨비나")

    # when: 이름을 바꾼다
    action_type.rename("세미나", later(5))

    # then: 참조의 이름도 바뀐다
    assert action_type.ref.name == "세미나"


def test_used_action_type_cannot_be_deleted_and_the_message_has_the_count() -> None:
    """사용 중인 유형은 삭제할 수 없고 문구에 건수가 들어 있다."""
    # given: 유형
    action_type = make_action_type()

    # when·then: Action 3건이 쓰는 유형을 삭제하려 하면 건수가 담긴 문구로 거부된다
    with raises_with(ActionTypeInUseError, "사용 중인 유형은 삭제할 수 없습니다. (Action 3건)"):
        action_type.ensure_deletable(3)


def test_in_use_error_keeps_the_usage_count() -> None:
    """사용 중 오류는 사용 건수를 가진다."""
    # when: 2건이 쓰는 유형의 삭제 가능 여부를 확인한다
    with pytest.raises(ActionTypeInUseError) as raised:
        make_action_type().ensure_deletable(2)

    # then: 오류가 사용 건수 2를 가진다
    assert raised.value.usage == 2


def test_unused_action_type_is_deletable_even_when_it_is_a_default() -> None:
    """쓰이지 않으면 기본 유형도 삭제할 수 있다."""
    # when·then: 사용 0건인 기본 유형은 삭제 가능 확인이 통과한다
    make_action_type("기타", is_default=True, default_order=8).ensure_deletable(0)


def test_action_type_errors_map_to_not_found_conflict_invalid_state_and_invalid_value() -> None:
    """유형 오류는 없음·중복·상태·값 오류 계열에 속한다."""
    # when·then: 각 오류 클래스의 계열을 확인한다
    assert issubclass(ActionTypeNotFoundError, NotFoundError)
    assert issubclass(DuplicateActionTypeNameError, AlreadyExistsError)
    assert issubclass(ActionTypeInUseError, InvalidStateError)
    assert issubclass(UnknownActionTypeError, InvalidValueError)


def test_error_messages_are_the_user_text() -> None:
    """오류 문구는 사용자에게 보이는 문구다."""
    # when·then: 각 오류를 문자열로 만든다
    assert str(DuplicateActionTypeNameError("데모")) == "이미 있는 유형 이름입니다."
    assert str(UnknownActionTypeError()) == "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
    assert str(ActionTypeNotFoundError(new_id())).startswith("Action 유형")


def test_not_found_error_keeps_the_identifier() -> None:
    """없음 오류는 찾던 식별자를 가진다."""
    # given: 찾던 유형 id
    type_id = ActionTypeId(new_id())

    # when·then: 그 id로 만든 오류가 식별자를 가진다
    assert ActionTypeNotFoundError(type_id).identifier == type_id
