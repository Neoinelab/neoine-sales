"""R1 AC1-1·1-5·1-7: User.change_role은 역할을 바꾸고 수정 시각을 갱신한다. 같은 역할은 그대로."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW, later
from tests.factories_auth import make_resigned_user, make_user
from tests.support.expect import raises_with


def test_change_role_to_another_role_updates_role_and_touches() -> None:
    user = make_user("kim", Role.SALES)

    changed = user.change_role(Role.USER, later(60))

    assert changed is True
    assert user.role is Role.USER
    assert user.updated_at == later(60)


def test_change_role_to_same_role_returns_false_without_touch() -> None:
    user = make_user("kim", Role.SALES)

    changed = user.change_role(Role.SALES, later(60))

    assert changed is False
    assert user.role is Role.SALES
    assert user.updated_at == NOW


def test_change_role_of_resigned_user_raises_invalid_state() -> None:
    user = make_resigned_user("kim", Role.SALES)
    before = user.updated_at

    with raises_with(InvalidStateError, "이미 퇴사 처리된 사용자입니다"):
        user.change_role(Role.ADMIN, later(3600))

    assert user.role is Role.SALES
    assert user.updated_at == before


@pytest.mark.parametrize("new_role", [Role.ADMIN, Role.SALES, Role.USER])
def test_change_role_keeps_identity_fields(new_role: Role) -> None:
    user = make_user("kim", Role.USER)
    login_id, user_id, created_at = user.login_id, user.id, user.created_at

    user.change_role(new_role, later(5))

    assert (user.login_id, user.id, user.created_at) == (login_id, user_id, created_at)
