"""Action 유형 이름 규칙과 참조 값 객체: trim, 필수, 50자, NUL."""

import pytest

from app.domain.action_type.values import (
    ACTION_TYPE_NAME_MAX,
    ACTION_TYPE_REQUIRED,
    ACTION_TYPE_TOO_LONG,
    ActionTypeId,
    ActionTypeRef,
    normalize_action_type_name,
)
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with
from tests.support.ids import new_id


def test_action_type_name_limit_is_50() -> None:
    """유형 이름 상한은 50자다."""
    # when·then: 상수를 확인한다
    assert ACTION_TYPE_NAME_MAX == 50


def test_action_type_name_is_trimmed() -> None:
    """이름은 앞뒤 공백을 지운다."""
    # when·then: 공백으로 감싼 이름을 정리한다
    assert normalize_action_type_name("  데모  ") == "데모"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_blank_action_type_name_is_rejected(raw: str) -> None:
    """비었거나 공백뿐인 이름은 거부한다."""
    # when·then: 빈 입력은 필수 문구로 거부된다
    with raises_with(InvalidValueError, "유형을 입력하세요."):
        normalize_action_type_name(raw)


def test_the_required_and_too_long_messages_are_the_user_text() -> None:
    """필수·길이 초과 문구는 사용자에게 보이는 문구다."""
    # when·then: 상수 문구를 확인한다
    assert ACTION_TYPE_REQUIRED == "유형을 입력하세요."
    assert ACTION_TYPE_TOO_LONG == "유형은 50자 이내로 입력하세요."


def test_action_type_name_allows_50_code_points_even_when_they_are_emoji() -> None:
    """이모지 50개도 50자로 세어 허용한다."""
    # when·then: 이모지 50개 이름이 그대로 통과한다
    assert normalize_action_type_name("😀" * 50) == "😀" * 50


def test_action_type_name_of_51_code_points_is_rejected() -> None:
    """51자 이름은 거부한다."""
    # when·then: 51자를 정리하면 길이 문구로 거부된다
    with raises_with(InvalidValueError, "유형은 50자 이내로 입력하세요."):
        normalize_action_type_name("가" * 51)


def test_length_is_counted_after_trimming() -> None:
    """길이는 공백을 지운 뒤에 센다."""
    # when·then: 공백 포함 52자라도 정리 뒤 50자면 통과한다
    assert normalize_action_type_name(" " + "가" * 50 + " ") == "가" * 50


def test_nul_in_action_type_name_is_rejected_even_when_surrounded_by_spaces() -> None:
    """공백으로 감싸도 이름 속 NUL은 거부한다."""
    # when·then: NUL이 든 이름은 거부된다
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_action_type_name(" 데\x00모 ")


def test_blank_is_reported_before_length() -> None:
    """공백뿐인 긴 이름은 길이보다 필수 오류가 먼저다."""
    # when·then: 공백 60자는 필수 문구로 거부된다
    with raises_with(InvalidValueError, ACTION_TYPE_REQUIRED):
        normalize_action_type_name(" " * 60)


def test_type_ref_is_a_value_of_id_and_name() -> None:
    """유형 참조는 id와 이름이 모두 같을 때만 같은 값이다."""
    # given: 유형 id
    type_id = ActionTypeId(new_id())

    # when·then: id·이름이 같으면 같고 하나라도 다르면 다르다
    assert ActionTypeRef(type_id, "미팅") == ActionTypeRef(type_id, "미팅")
    assert ActionTypeRef(type_id, "미팅") != ActionTypeRef(type_id, "회의")
    assert ActionTypeRef(type_id, "미팅") != ActionTypeRef(ActionTypeId(new_id()), "미팅")
    assert hash(ActionTypeRef(type_id, "미팅")) == hash(ActionTypeRef(type_id, "미팅"))
