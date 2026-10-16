"""AC8: 사용자 표기(label)는 UserRef 한 곳에서 만든다. 퇴사자는 `이름(퇴사)`."""

import dataclasses
from uuid import uuid4

import pytest

from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserDeleteReason, UserId, UserRef
from tests.factories import later
from tests.factories_auth import make_resigned_user, make_user


def test_label_is_the_name_for_an_active_user() -> None:
    ref = UserRef(id=UserId(uuid4()), name="홍길동", resigned=False, role=Role.SALES)

    assert ref.label == "홍길동"


def test_label_adds_resigned_suffix_for_a_resigned_user() -> None:
    ref = UserRef(id=UserId(uuid4()), name="홍길동", resigned=True, role=Role.SALES)

    assert ref.label == "홍길동(퇴사)"


def test_user_ref_of_an_active_user_uses_display_name() -> None:
    user = make_user("hong")
    user.record_login(later(1), display_name="홍길동", email=None)

    ref = user.to_ref()

    assert (ref.id, ref.name, ref.resigned) == (user.id, "홍길동", False)
    assert ref.label == "홍길동"


def test_user_ref_has_only_id_name_resigned_and_role_fields_and_no_login_id() -> None:
    names = {f.name for f in dataclasses.fields(UserRef)}
    ref = make_user("hong").to_ref()

    assert names == {"id", "name", "resigned", "role"}
    assert not hasattr(ref, "login_id")


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
def test_user_ref_carries_the_role_of_the_user(role: Role) -> None:
    ref = make_user("hong", role).to_ref()

    assert ref.role is role


def test_user_ref_of_a_resigned_user_still_carries_the_role() -> None:
    ref = make_resigned_user("hong", Role.SALES).to_ref()

    assert (ref.resigned, ref.role) == (True, Role.SALES)


def test_user_ref_name_falls_back_to_login_id_without_display_name() -> None:
    ref = make_user("hong").to_ref()

    assert ref.name == "hong"
    assert ref.label == "hong"


def test_user_ref_of_a_resigned_user_is_flagged_and_labelled() -> None:
    user = make_user("hong")
    user.record_login(later(1), display_name="홍길동", email=None)
    user.resign(later(2))

    ref = user.to_ref()

    assert ref.resigned is True
    assert ref.label == "홍길동(퇴사)"


def test_user_ref_is_immutable() -> None:
    ref = make_user("hong").to_ref()

    with pytest.raises(AttributeError):
        ref.name = "다른 이름"  # type: ignore[misc]


def test_delete_reason_values_are_a_closed_set() -> None:
    assert {reason.value for reason in UserDeleteReason} == {"resigned"}
