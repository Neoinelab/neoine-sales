"""등록 시 선택 display_name. 길이는 NAME_MAX, NUL 불가, 등록 입력은 자르지 않고 거절한다."""

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import NAME_MAX, Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.entities import User
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.support.ids import new_id


def _register(display_name: str | None) -> User:
    return User.register(
        LoginId("kim"),
        Role.USER,
        entity_id=UserId(new_id()),
        now=NOW,
        display_name=display_name,
    )


def test_register_with_a_display_name_keeps_it_before_any_login() -> None:
    """등록 때 준 이름은 로그인 전에도 이름으로 쓰인다

    테스트 코드: US-012
    """
    # when: 이름을 주고 등록한다
    user = _register("김영업")

    # then: 이름이 저장되고 참조·principal 이름이 된다
    assert user.display_name == "김영업"
    assert user.last_login_at is None
    assert user.to_ref().name == "김영업"
    assert user.to_principal().name == "김영업"


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_register_without_a_usable_display_name_leaves_it_unset(value: str | None) -> None:
    """이름이 없거나 공백뿐이면 이름 없음이다

    테스트 코드: US-012
    """
    # when: 쓸 수 없는 이름으로 등록한다
    user = _register(value)

    # then: 이름이 None이고 참조 이름은 아이디다
    assert user.display_name is None
    assert user.to_ref().name == "kim"


def test_register_trims_surrounding_whitespace_of_the_display_name() -> None:
    """이름의 앞뒤 공백은 지워진다

    테스트 코드: US-013
    """
    # when: 앞뒤 공백이 있는 이름으로 등록한다
    display_name = _register("  김영업 \t").display_name
    # then: 공백 없는 이름이다
    assert display_name == "김영업"


def test_register_keeps_inner_whitespace_of_the_display_name() -> None:
    """이름 안쪽 공백은 그대로 둔다"""
    # when: 안쪽 공백이 있는 이름으로 등록한다
    display_name = _register("김 영업").display_name
    # then: 안쪽 공백이 남는다
    assert display_name == "김 영업"


def test_register_accepts_a_display_name_of_exactly_name_max() -> None:
    """최대 길이 이름은 허용된다

    테스트 코드: US-013
    """
    # when: 200자 이름으로 등록한다
    display_name = _register("가" * NAME_MAX).display_name
    # then: 그대로 저장된다
    assert display_name == "가" * NAME_MAX


def test_register_accepts_name_max_after_trimming_the_padding() -> None:
    """공백을 지운 뒤 200자이면 허용된다

    테스트 코드: US-013
    """
    # when: 공백이 붙은 200자 이름으로 등록한다
    display_name = _register(" " + "가" * NAME_MAX + " ").display_name
    # then: 200자로 저장된다
    assert display_name == "가" * NAME_MAX


def test_register_rejects_a_display_name_longer_than_name_max_instead_of_truncating() -> None:
    """최대 길이를 넘는 이름은 자르지 않고 거절한다

    테스트 코드: US-014
    """
    # when: 201자 이름으로 등록한다
    with pytest.raises(InvalidValueError):
        _register("가" * (NAME_MAX + 1))
    # then: 입력 오류다


@pytest.mark.parametrize("value", ["a\x00b", "\x00", " \x00 "])
def test_register_rejects_a_display_name_containing_nul(value: str) -> None:
    """NUL이 든 이름은 거절한다

    테스트 코드: US-014
    """
    # when: NUL이 든 이름으로 등록한다
    with pytest.raises(InvalidValueError):
        _register(value)
    # then: 입력 오류다


def test_record_login_overwrites_the_display_name_given_at_registration() -> None:
    """로그인 기록은 등록 때 준 표시 이름을 덮어쓴다."""
    # given: 임시 이름으로 등록한 사용자
    user = _register("임시 이름")

    # when: AD 이름으로 로그인을 기록한다
    user.record_login(later(5), display_name="AD 이름", email=None)

    # then: 표시 이름이 AD 이름이다
    assert user.display_name == "AD 이름"
