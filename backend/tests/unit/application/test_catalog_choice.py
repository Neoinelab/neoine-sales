"""CatalogChoice: 카탈로그 항목 선택은 id 또는 name 중 정확히 하나다."""

from app.application.choice import CatalogChoice
from app.domain.common.errors import InvalidValueError
from tests.support.expect import raises_with
from tests.support.ids import new_id

ONLY_ONE = "id와 name 중 하나만 보내세요."


def test_choice_with_only_an_id_is_accepted() -> None:
    """id만 가진 선택은 만들어진다.

    테스트 코드: CL-063
    """
    # given: 유형 id
    type_id = new_id()

    # when: id만 담은 선택을 만든다
    choice = CatalogChoice(id=type_id)

    # then: id만 있고 name은 없다
    assert (choice.id, choice.name) == (type_id, None)


def test_choice_with_only_a_name_is_accepted() -> None:
    """name만 가진 선택은 만들어진다.

    테스트 코드: CL-063
    """
    # when: name만 담은 선택을 만든다
    choice = CatalogChoice(name="데모")

    # then: name만 있고 id는 없다
    assert (choice.id, choice.name) == (None, "데모")


def test_choice_requires_exactly_one_of_id_and_name_when_both_are_given() -> None:
    """id와 name을 둘 다 담으면 거절한다.

    테스트 코드: CL-063
    """
    # when·then: 둘 다 담은 선택을 만든다 → 'id와 name 중 하나만 보내세요.' 오류다
    with raises_with(InvalidValueError, ONLY_ONE):
        CatalogChoice(id=new_id(), name="데모")


def test_choice_requires_exactly_one_of_id_and_name_when_neither_is_given() -> None:
    """id도 name도 없으면 거절한다.

    테스트 코드: CL-063
    """
    # when·then: 아무것도 담지 않은 선택을 만든다 → 'id와 name 중 하나만 보내세요.' 오류다
    with raises_with(InvalidValueError, ONLY_ONE):
        CatalogChoice()


def test_an_empty_name_is_still_a_name_and_is_judged_by_the_name_rule_later() -> None:
    """빈 문자열은 이름을 보낸 것이므로 선택 자체는 만들어지고 판정은 이름 규칙이 한다.

    테스트 코드: CL-065
    """
    # when: 빈 name 선택을 만든다
    name = CatalogChoice(name="").name
    # then: name이 빈 문자열인 선택이다
    assert name == ""


def test_choices_are_values() -> None:
    """선택은 값 객체라서 같은 내용이면 같고 다르면 다르다."""
    # given: 같은 id로 만든 선택 둘과 name이 다른 선택 둘
    type_id = new_id()

    # when: 서로 비교한다
    actual = CatalogChoice(id=type_id)
    # then: 같은 것은 같고 다른 것은 다르다
    assert actual == CatalogChoice(id=type_id)
    assert CatalogChoice(name="a") != CatalogChoice(name="b")
