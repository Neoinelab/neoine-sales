"""역할별 권한 묶음(PL-R1, PL-001). admin=전부, sales=READ·WRITE, user=READ."""

import pytest

from app.domain.auth.principal import Permission, Principal, Role
from tests.support.user_ids import uid

MATRIX = {
    Role.ADMIN: {Permission.READ, Permission.WRITE, Permission.ADMINISTER},
    Role.SALES: {Permission.READ, Permission.WRITE},
    Role.USER: {Permission.READ},
}


def test_role_has_exactly_three_members() -> None:
    """역할 값은 정확히 admin·sales·user 세 개다.

    테스트 코드: PL-001
    """
    # when: 역할 값을 모은다
    values = {role.value for role in Role}
    # then: 세 개다
    assert values == {"admin", "sales", "user"}


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_role_allows_exactly_the_permissions_in_the_matrix(
    role: Role, permission: Permission
) -> None:
    """역할은 정해진 권한 묶음만 허용한다.

    테스트 코드: PL-001
    """
    # when: 역할에 권한을 물어본다
    allowed = role.allows(permission)
    # then: admin은 셋 다, sales는 read·write만, user는 read만 허용된다
    assert allowed is (permission in MATRIX[role])


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize("permission", list(Permission))
def test_principal_can_follows_its_role(role: Role, permission: Permission) -> None:
    """Principal.can은 역할의 권한 묶음과 같은 답을 한다.

    테스트 코드: PL-001
    """
    # given: 그 역할의 Principal
    principal = Principal(uid("kim"), "kim", "kim@corp.test", "김영업", role)
    # when: 권한을 물어본다
    can = principal.can(permission)
    # then: 역할과 같은 답이다
    assert can is (permission in MATRIX[role])


def test_role_user_is_constructible_from_its_value() -> None:
    """역할은 값 문자열로 만들 수 있다."""
    # when: 값 "user"로 역할을 만든다
    role = Role("user")
    # then: Role.USER다
    assert role is Role.USER
