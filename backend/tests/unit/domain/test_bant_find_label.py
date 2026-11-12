"""BANT `find_label`: 같은 구분 목록에서 대소문자 무시 완전 일치로 Label을 찾는다."""

from app.domain.bant.rules import find_label
from app.domain.bant.values import BantCategory
from tests.factories_catalog import make_label


def test_find_label_matches_ignoring_case_within_category() -> None:
    """같은 구분 안에서 대소문자를 무시하고 Label을 찾는다."""
    # given: 같은 구분의 Label 두 개
    label = make_label(BantCategory.BUDGET, name="Full Budget")
    siblings = [make_label(BantCategory.BUDGET, name="예산 없음"), label]
    # when: 대소문자가 다른 이름으로 찾는다
    found = find_label(siblings, "full budget")
    # then: 저장된 Label이 나온다
    assert found is label


def test_find_label_returns_the_stored_spelling() -> None:
    """찾은 Label은 저장된 표기 그대로 돌려준다."""
    # when: 소문자로 Label을 찾는다
    found = find_label([make_label(BantCategory.NEED, name="CISO 지시")], "ciso 지시")
    # then: 저장된 표기 그대로다
    assert found is not None
    assert found.name == "CISO 지시"


def test_find_label_returns_none_without_match() -> None:
    """완전히 일치하는 이름이 없거나 목록이 비면 None이다."""
    # given: 예산 없음 Label 하나
    siblings = [make_label(BantCategory.BUDGET, name="예산 없음")]
    # when: 부분 일치하는 이름이나 빈 목록에서 라벨을 찾는다
    result = find_label(siblings, "예산")
    # then: 찾지 못해 None이다
    assert result is None
    assert find_label([], "예산 없음") is None
