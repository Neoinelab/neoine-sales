"""R1 AC1-3·1-4·1-5: 역할 변경 정책(퇴사 -> 자기 자신 -> 마지막 admin 강등 순서)."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from app.domain.user import policy
from tests.factories_auth import make_resigned_user, make_user
from tests.support.expect import raises_with
from tests.support.user_ids import uid

SELF_CHANGE = "자기 자신의 역할은 바꿀 수 없습니다."
LAST_ADMIN = "마지막 관리자의 역할은 바꿀 수 없습니다."
RESIGNED = "이미 퇴사 처리된 사용자입니다"


def test_role_change_of_oneself_is_rejected() -> None:
    target = make_user("kim", Role.SALES)

    with raises_with(InvalidStateError, SELF_CHANGE):
        policy.ensure_role_changeable(
            target, Role.USER, actor_user_id=target.id, active_admin_count=3
        )


def test_demoting_the_last_active_admin_is_rejected() -> None:
    target = make_user("boss", Role.ADMIN)

    with raises_with(InvalidStateError, LAST_ADMIN):
        policy.ensure_role_changeable(
            target, Role.SALES, actor_user_id=uid("other"), active_admin_count=1
        )


@pytest.mark.parametrize("new_role", [Role.SALES, Role.USER])
def test_demoting_an_admin_is_allowed_while_another_admin_remains(new_role: Role) -> None:
    target = make_user("boss", Role.ADMIN)

    policy.ensure_role_changeable(
        target, new_role, actor_user_id=uid("other"), active_admin_count=2
    )


def test_keeping_the_last_admin_as_admin_is_allowed() -> None:
    target = make_user("boss", Role.ADMIN)

    policy.ensure_role_changeable(
        target, Role.ADMIN, actor_user_id=uid("other"), active_admin_count=1
    )


def test_promoting_to_admin_ignores_admin_count() -> None:
    target = make_user("kim", Role.USER)

    policy.ensure_role_changeable(
        target, Role.ADMIN, actor_user_id=uid("boss"), active_admin_count=1
    )


@pytest.mark.parametrize("new_role", [Role.ADMIN, Role.USER])
def test_non_admin_target_is_changeable_even_with_one_admin(new_role: Role) -> None:
    target = make_user("kim", Role.SALES)

    policy.ensure_role_changeable(target, new_role, actor_user_id=uid("boss"), active_admin_count=1)


def test_role_change_of_resigned_user_is_rejected_first() -> None:
    target = make_resigned_user("kim", Role.ADMIN)

    with raises_with(InvalidStateError, RESIGNED):
        policy.ensure_role_changeable(
            target, Role.USER, actor_user_id=target.id, active_admin_count=1
        )


def test_self_check_precedes_the_last_admin_check() -> None:
    target = make_user("boss", Role.ADMIN)

    with raises_with(InvalidStateError, SELF_CHANGE):
        policy.ensure_role_changeable(
            target, Role.SALES, actor_user_id=target.id, active_admin_count=1
        )


def test_actor_without_a_user_row_is_not_treated_as_self() -> None:
    target = make_user("kim", Role.SALES)

    policy.ensure_role_changeable(target, Role.USER, actor_user_id=None, active_admin_count=2)
