"""삭제 정책(USER-5·6, AC5): 자기 자신·마지막 활성 admin 보호(퇴사·물리 삭제 공통)."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import DomainError, InvalidStateError
from app.domain.user.policy import ensure_deletable
from tests.factories_auth import make_user
from tests.support.user_ids import uid


def test_cannot_delete_self() -> None:
    target = make_user("kim", Role.SALES)

    with pytest.raises(InvalidStateError):
        ensure_deletable(target, actor_user_id=target.id, active_admin_count=3)


def test_cannot_delete_last_admin() -> None:
    target = make_user("boss", Role.ADMIN)

    with pytest.raises(InvalidStateError):
        ensure_deletable(target, actor_user_id=uid("other"), active_admin_count=1)


def test_can_delete_admin_when_another_admin_remains() -> None:
    target = make_user("boss", Role.ADMIN)

    ensure_deletable(target, actor_user_id=uid("other"), active_admin_count=2)


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
def test_can_delete_non_admin_even_when_only_one_admin_exists(role: Role) -> None:
    target = make_user("worker", role)

    ensure_deletable(target, actor_user_id=uid("boss"), active_admin_count=1)


def test_actor_without_a_user_row_is_not_treated_as_self() -> None:
    target = make_user("kim", Role.SALES)

    ensure_deletable(target, actor_user_id=None, active_admin_count=2)


def test_deletion_errors_are_domain_errors() -> None:
    target = make_user("kim", Role.ADMIN)

    with pytest.raises(DomainError):
        ensure_deletable(target, actor_user_id=target.id, active_admin_count=1)
