"""삭제 정책(USER-5·6, AC5): 자기 자신·마지막 활성 admin 보호(퇴사·물리 삭제 공통)."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import DomainError, InvalidStateError
from app.domain.user.policy import ensure_deletable
from tests.factories_auth import make_user
from tests.support.user_ids import uid


def test_cannot_delete_self() -> None:
    """자기 자신은 삭제할 수 없다

    테스트 코드: US-065
    """
    # given: 요청자와 대상이 같은 사용자
    target = make_user("kim", Role.SALES)

    # when: 삭제 가능 여부를 확인한다
    with pytest.raises(InvalidStateError):
        ensure_deletable(target, actor_user_id=target.id, active_admin_count=3)
    # then: 상태 오류다


def test_cannot_delete_last_admin() -> None:
    """재직 admin이 하나뿐이면 그 admin은 삭제할 수 없다

    테스트 코드: US-066
    """
    # given: admin 대상, 재직 admin 1명
    target = make_user("boss", Role.ADMIN)

    # when: 삭제 가능 여부를 확인한다
    with pytest.raises(InvalidStateError):
        ensure_deletable(target, actor_user_id=uid("other"), active_admin_count=1)
    # then: 상태 오류다


def test_can_delete_admin_when_another_admin_remains() -> None:
    """재직 admin이 둘이면 다른 admin은 삭제할 수 있다

    테스트 코드: US-067
    """
    # given: admin 대상, 재직 admin 2명
    target = make_user("boss", Role.ADMIN)

    # when: 삭제 가능 여부를 확인한다
    ensure_deletable(target, actor_user_id=uid("other"), active_admin_count=2)
    # then: 예외 없이 통과한다


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
def test_can_delete_non_admin_even_when_only_one_admin_exists(role: Role) -> None:
    """admin이 아닌 대상은 admin이 하나뿐이어도 삭제할 수 있다"""
    # given: sales 또는 user 대상, 재직 admin 1명
    target = make_user("worker", role)

    # when: 삭제 가능 여부를 확인한다
    ensure_deletable(target, actor_user_id=uid("boss"), active_admin_count=1)
    # then: 예외 없이 통과한다


def test_actor_without_a_user_row_is_not_treated_as_self() -> None:
    """요청자 행이 없으면 자기 자신으로 보지 않는다"""
    # given: 요청자 id 없음
    target = make_user("kim", Role.SALES)

    # when: 삭제 가능 여부를 확인한다
    ensure_deletable(target, actor_user_id=None, active_admin_count=2)
    # then: 예외 없이 통과한다


def test_deletion_errors_are_domain_errors() -> None:
    """삭제 거절은 도메인 오류다"""
    # given: 자기 자신이 마지막 admin인 대상
    target = make_user("kim", Role.ADMIN)

    # when: 삭제 가능 여부를 확인한다
    with pytest.raises(DomainError):
        ensure_deletable(target, actor_user_id=target.id, active_admin_count=1)
    # then: 도메인 오류다
