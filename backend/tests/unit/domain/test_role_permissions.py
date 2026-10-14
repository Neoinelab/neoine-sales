"""T-D1: 역할별 권한 매트릭스(ROLE-1~3, SET-7). admin=전부, sales=READ·WRITE, user=READ."""

import pytest

from app.domain.auth.principal import Permission, Principal, Role
from tests.support.user_ids import uid

MATRIX = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.ADMINISTER},
    Role.SALES: {Permission.READ, Permission.WRITE},
    Role.USER: {Permission.READ},
}


def test_role_has_three_members() -> None:
    assert {role.value for role in Role} == {"admin", "sales", "user"}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_role_allows_exactly_the_permissions_in_the_matrix(
    role: Role, permission: Permission
) -> None:
    assert role.allows(permission) is (permission in MATRIX[role])


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_principal_can_follows_its_role(role: Role, permission: Permission) -> None:
    principal = Principal(uid("kim"), "kim", "kim@corp.test", "김영업", role)

    assert principal.can(permission) is (permission in MATRIX[role])


def test_role_user_is_constructible_from_its_value() -> None:
    assert Role("user") is Role.USER
