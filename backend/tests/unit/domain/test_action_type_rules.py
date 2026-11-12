"""Action 유형 규칙: 이름 찾기(대소문자 무시 완전 일치)와 중복 거부."""

import pytest

from app.domain.action_type.errors import DuplicateActionTypeNameError
from app.domain.action_type.rules import ensure_unique_action_type_name, find_action_type
from tests.factories_action_type import make_action_type


def test_find_matches_ignoring_case() -> None:
    """이름 찾기는 대소문자를 무시한다."""
    # given: "미팅"과 "Demo" 유형
    demo = make_action_type("Demo")

    # when·then: "dEMO"로 찾으면 Demo가 나온다
    assert find_action_type([make_action_type("미팅"), demo], "dEMO") is demo


def test_find_returns_the_stored_spelling_not_the_input() -> None:
    """찾으면 입력이 아니라 저장된 표기를 돌려준다."""
    # when: "DEMO"로 찾는다
    found = find_action_type([make_action_type("Demo")], "DEMO")

    # then: 저장된 표기 "Demo"가 나온다
    assert found is not None
    assert found.name == "Demo"


def test_find_returns_none_for_partial_match() -> None:
    """부분 일치는 찾지 못한다."""
    # when·then: 앞부분만 또는 더 길게 입력하면 None이다
    assert find_action_type([make_action_type("데모 시연")], "데모") is None
    assert find_action_type([make_action_type("데모")], "데모 시연") is None


def test_find_returns_none_for_an_empty_catalog() -> None:
    """빈 카탈로그에서는 찾지 못한다."""
    # when·then: 빈 목록에서 찾으면 None이다
    assert find_action_type([], "데모") is None


def test_duplicate_name_ignoring_case_is_rejected() -> None:
    """대소문자만 다른 이름은 중복이다."""
    # when·then: "Demo"가 있는데 "demo"를 쓰면 중복 오류다
    with pytest.raises(DuplicateActionTypeNameError):
        ensure_unique_action_type_name([make_action_type("Demo")], "demo")


def test_a_different_name_is_accepted() -> None:
    """다른 이름은 받아들인다."""
    # when·then: "Demo"가 있어도 "Demo2"는 통과한다
    ensure_unique_action_type_name([make_action_type("Demo")], "Demo2")


def test_renaming_to_own_name_in_other_case_is_allowed() -> None:
    """자기 이름의 대소문자만 바꾸는 이름 변경은 허용한다."""
    # given: "Demo" 유형
    mine = make_action_type("Demo")

    # when·then: 자기 id를 주고 "DEMO"로 바꾸면 통과한다
    ensure_unique_action_type_name([mine], "DEMO", self_id=mine.id)


def test_renaming_still_conflicts_with_other_types_when_self_is_given() -> None:
    """자기 id를 줘도 다른 유형의 이름과는 중복이다."""
    # given: "가"와 "나" 유형
    mine = make_action_type("가")
    other = make_action_type("나")

    # when·then: "가"를 "나"로 바꾸면 중복 오류다
    with pytest.raises(DuplicateActionTypeNameError):
        ensure_unique_action_type_name([mine, other], "나", self_id=mine.id)
