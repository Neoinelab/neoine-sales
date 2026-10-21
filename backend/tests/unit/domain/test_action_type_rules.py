"""Action 유형 규칙(AC-4·9·10): 이름 찾기(대소문자 무시 완전 일치)와 중복 거부."""

import pytest

from app.domain.action_type.errors import DuplicateActionTypeNameError
from app.domain.action_type.rules import ensure_unique_action_type_name, find_action_type
from tests.factories_action_type import make_action_type


def test_find_matches_ignoring_case() -> None:
    demo = make_action_type("Demo")

    assert find_action_type([make_action_type("미팅"), demo], "dEMO") is demo


def test_find_returns_the_stored_spelling_not_the_input() -> None:
    found = find_action_type([make_action_type("Demo")], "DEMO")

    assert found is not None
    assert found.name == "Demo"


def test_find_returns_none_for_partial_match() -> None:
    assert find_action_type([make_action_type("데모 시연")], "데모") is None
    assert find_action_type([make_action_type("데모")], "데모 시연") is None


def test_find_returns_none_for_an_empty_catalog() -> None:
    assert find_action_type([], "데모") is None


def test_duplicate_name_ignoring_case_is_rejected() -> None:
    with pytest.raises(DuplicateActionTypeNameError):
        ensure_unique_action_type_name([make_action_type("Demo")], "demo")


def test_a_different_name_is_accepted() -> None:
    ensure_unique_action_type_name([make_action_type("Demo")], "Demo2")


def test_renaming_to_own_name_in_other_case_is_allowed() -> None:
    mine = make_action_type("Demo")

    ensure_unique_action_type_name([mine], "DEMO", self_id=mine.id)


def test_renaming_still_conflicts_with_other_types_when_self_is_given() -> None:
    mine = make_action_type("가")
    other = make_action_type("나")

    with pytest.raises(DuplicateActionTypeNameError):
        ensure_unique_action_type_name([mine, other], "나", self_id=mine.id)
