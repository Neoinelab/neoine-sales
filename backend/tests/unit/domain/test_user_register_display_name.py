"""AC-25: 등록 시 선택 display_name. 길이는 NAME_MAX, NUL 불가, 등록 입력은 자르지 않고 거절한다."""

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import NAME_MAX, Role
from app.domain.common.errors import InvalidValueError
from app.domain.user.entities import User
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.support.ids import new_id
from tests.support.user_ids import uid


def _register(display_name: str | None) -> User:
    return User.register(
        LoginId("kim"),
        Role.USER,
        entity_id=UserId(new_id()),
        created_by_user_id=uid("admin1"),
        now=NOW,
        display_name=display_name,
    )


def test_register_with_a_display_name_keeps_it_before_any_login() -> None:
    user = _register("김영업")

    assert user.display_name == "김영업"
    assert user.last_login_at is None
    assert user.to_ref().name == "김영업"
    assert user.to_principal().name == "김영업"


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_register_without_a_usable_display_name_leaves_it_unset(value: str | None) -> None:
    user = _register(value)

    assert user.display_name is None
    assert user.to_ref().name == "kim"


def test_register_trims_surrounding_whitespace_of_the_display_name() -> None:
    assert _register("  김영업 \t").display_name == "김영업"


def test_register_keeps_inner_whitespace_of_the_display_name() -> None:
    assert _register("김 영업").display_name == "김 영업"


def test_register_accepts_a_display_name_of_exactly_name_max() -> None:
    assert _register("가" * NAME_MAX).display_name == "가" * NAME_MAX


def test_register_accepts_name_max_after_trimming_the_padding() -> None:
    assert _register(" " + "가" * NAME_MAX + " ").display_name == "가" * NAME_MAX


def test_register_rejects_a_display_name_longer_than_name_max_instead_of_truncating() -> None:
    with pytest.raises(InvalidValueError):
        _register("가" * (NAME_MAX + 1))


@pytest.mark.parametrize("value", ["a\x00b", "\x00", " \x00 "])
def test_register_rejects_a_display_name_containing_nul(value: str) -> None:
    with pytest.raises(InvalidValueError):
        _register(value)


def test_record_login_overwrites_the_display_name_given_at_registration() -> None:
    user = _register("임시 이름")

    user.record_login(later(5), display_name="AD 이름", email=None)

    assert user.display_name == "AD 이름"
