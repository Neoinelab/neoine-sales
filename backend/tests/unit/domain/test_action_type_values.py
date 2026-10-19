"""Action 유형 이름 규칙(AC-3)과 참조 값 객체: trim, 필수, 50자, NUL."""

from uuid import uuid4

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


def test_action_type_name_limit_is_50() -> None:
    assert ACTION_TYPE_NAME_MAX == 50


def test_action_type_name_is_trimmed() -> None:
    assert normalize_action_type_name("  데모  ") == "데모"


@pytest.mark.parametrize("raw", ["", "   ", "\t\n"], ids=["empty", "spaces", "tab-newline"])
def test_blank_action_type_name_is_rejected(raw: str) -> None:
    with raises_with(InvalidValueError, "유형을 입력하세요."):
        normalize_action_type_name(raw)


def test_the_required_and_too_long_messages_are_the_user_text() -> None:
    assert ACTION_TYPE_REQUIRED == "유형을 입력하세요."
    assert ACTION_TYPE_TOO_LONG == "유형은 50자 이내로 입력하세요."


def test_action_type_name_allows_50_code_points_even_when_they_are_emoji() -> None:
    assert normalize_action_type_name("😀" * 50) == "😀" * 50


def test_action_type_name_of_51_code_points_is_rejected() -> None:
    with raises_with(InvalidValueError, "유형은 50자 이내로 입력하세요."):
        normalize_action_type_name("가" * 51)


def test_length_is_counted_after_trimming() -> None:
    assert normalize_action_type_name(" " + "가" * 50 + " ") == "가" * 50


def test_nul_in_action_type_name_is_rejected_even_when_surrounded_by_spaces() -> None:
    with pytest.raises(InvalidValueError, match="NUL"):
        normalize_action_type_name(" 데\x00모 ")


def test_blank_is_reported_before_length() -> None:
    with raises_with(InvalidValueError, ACTION_TYPE_REQUIRED):
        normalize_action_type_name(" " * 60)


def test_type_ref_is_a_value_of_id_and_name() -> None:
    type_id = ActionTypeId(uuid4())

    assert ActionTypeRef(type_id, "미팅") == ActionTypeRef(type_id, "미팅")
    assert ActionTypeRef(type_id, "미팅") != ActionTypeRef(type_id, "회의")
    assert ActionTypeRef(type_id, "미팅") != ActionTypeRef(ActionTypeId(uuid4()), "미팅")
    assert hash(ActionTypeRef(type_id, "미팅")) == hash(ActionTypeRef(type_id, "미팅"))
