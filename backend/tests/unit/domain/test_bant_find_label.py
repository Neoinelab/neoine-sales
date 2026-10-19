"""BANT `find_label`(AC-19): 같은 구분 목록에서 대소문자 무시 완전 일치로 Label을 찾는다."""

from app.domain.bant.rules import find_label
from app.domain.bant.values import BantCategory
from tests.factories_catalog import make_label


def test_find_label_matches_ignoring_case_within_category() -> None:
    label = make_label(BantCategory.BUDGET, name="Full Budget")
    siblings = [make_label(BantCategory.BUDGET, name="예산 없음"), label]

    assert find_label(siblings, "full budget") is label


def test_find_label_returns_the_stored_spelling() -> None:
    found = find_label([make_label(BantCategory.NEED, name="CISO 지시")], "ciso 지시")

    assert found is not None
    assert found.name == "CISO 지시"


def test_find_label_returns_none_without_match() -> None:
    siblings = [make_label(BantCategory.BUDGET, name="예산 없음")]

    assert find_label(siblings, "예산") is None
    assert find_label([], "예산 없음") is None
