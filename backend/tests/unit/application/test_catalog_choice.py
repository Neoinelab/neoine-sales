"""CatalogChoice(AC-7·17): 카탈로그 항목 선택은 id 또는 name 중 정확히 하나다."""

from uuid import uuid4

from app.application.choice import CatalogChoice

from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with

ONLY_ONE = "id와 name 중 하나만 보내세요."


def test_choice_with_only_an_id_is_accepted() -> None:
    type_id = uuid4()

    choice = CatalogChoice(id=type_id)

    assert (choice.id, choice.name) == (type_id, None)


def test_choice_with_only_a_name_is_accepted() -> None:
    choice = CatalogChoice(name="데모")

    assert (choice.id, choice.name) == (None, "데모")


def test_choice_requires_exactly_one_of_id_and_name_when_both_are_given() -> None:
    with raises_with(InvalidValueError, ONLY_ONE):
        CatalogChoice(id=uuid4(), name="데모")


def test_choice_requires_exactly_one_of_id_and_name_when_neither_is_given() -> None:
    with raises_with(InvalidValueError, ONLY_ONE):
        CatalogChoice()


def test_an_empty_name_is_still_a_name_and_is_judged_by_the_name_rule_later() -> None:
    """빈 문자열은 '이름을 보냈다'이므로 선택 객체 자체는 만들어진다(검증은 이름 규칙의 몫)."""
    assert CatalogChoice(name="").name == ""


def test_choices_are_values() -> None:
    type_id = uuid4()

    assert CatalogChoice(id=type_id) == CatalogChoice(id=type_id)
    assert CatalogChoice(name="a") != CatalogChoice(name="b")
