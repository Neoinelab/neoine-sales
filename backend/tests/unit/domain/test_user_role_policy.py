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
    """자기 자신의 역할은 바꿀 수 없다

    테스트 코드: US-034
    """
    # given: 요청자와 대상이 같은 사용자
    target = make_user("kim", Role.SALES)

    # when: 역할 변경 가능 여부를 확인한다
    with raises_with(InvalidStateError, SELF_CHANGE):
        policy.ensure_role_changeable(
            target, Role.USER, actor_user_id=target.id, active_admin_count=3
        )
    # then: 자기 자신 문구의 상태 오류다


def test_demoting_the_last_active_admin_is_rejected() -> None:
    """재직 admin이 하나뿐이면 강등할 수 없다

    테스트 코드: US-035
    """
    # given: admin 대상, 재직 admin 1명
    target = make_user("boss", Role.ADMIN)

    # when: 강등 가능 여부를 확인한다
    with raises_with(InvalidStateError, LAST_ADMIN):
        policy.ensure_role_changeable(
            target, Role.SALES, actor_user_id=uid("other"), active_admin_count=1
        )
    # then: 마지막 관리자 문구의 상태 오류다


@pytest.mark.parametrize("new_role", [Role.SALES, Role.USER])
def test_demoting_an_admin_is_allowed_while_another_admin_remains(new_role: Role) -> None:
    """재직 admin이 둘이면 다른 admin을 강등할 수 있다

    테스트 코드: US-033
    """
    # given: admin 대상, 재직 admin 2명
    target = make_user("boss", Role.ADMIN)

    # when: 강등 가능 여부를 확인한다
    policy.ensure_role_changeable(
        target, new_role, actor_user_id=uid("other"), active_admin_count=2
    )
    # then: 예외 없이 통과한다


def test_keeping_the_last_admin_as_admin_is_allowed() -> None:
    """마지막 admin을 admin으로 두는 것은 허용된다"""
    # given: admin 대상, 재직 admin 1명
    target = make_user("boss", Role.ADMIN)

    # when: 같은 admin으로 확인한다
    policy.ensure_role_changeable(
        target, Role.ADMIN, actor_user_id=uid("other"), active_admin_count=1
    )
    # then: 예외 없이 통과한다


def test_promoting_to_admin_ignores_admin_count() -> None:
    """admin으로 승격할 때는 admin 수를 따지지 않는다"""
    # given: user 대상, 재직 admin 1명
    target = make_user("kim", Role.USER)

    # when: admin으로 확인한다
    policy.ensure_role_changeable(
        target, Role.ADMIN, actor_user_id=uid("boss"), active_admin_count=1
    )
    # then: 예외 없이 통과한다


@pytest.mark.parametrize("new_role", [Role.ADMIN, Role.USER])
def test_non_admin_target_is_changeable_even_with_one_admin(new_role: Role) -> None:
    """admin이 아닌 대상은 admin이 하나뿐이어도 바꿀 수 있다"""
    # given: sales 대상, 재직 admin 1명
    target = make_user("kim", Role.SALES)

    # when: 역할 변경 가능 여부를 확인한다
    policy.ensure_role_changeable(target, new_role, actor_user_id=uid("boss"), active_admin_count=1)
    # then: 예외 없이 통과한다


def test_role_change_of_resigned_user_is_rejected_first() -> None:
    """퇴사자는 다른 규칙보다 먼저 퇴사 처리 오류로 거절된다

    테스트 코드: US-036
    """
    # given: 퇴사한 admin이 자기 자신을 대상으로
    target = make_resigned_user("kim", Role.ADMIN)

    # when: 역할 변경 가능 여부를 확인한다
    with raises_with(InvalidStateError, RESIGNED):
        policy.ensure_role_changeable(
            target, Role.USER, actor_user_id=target.id, active_admin_count=1
        )
    # then: 퇴사 처리 문구의 상태 오류다


def test_self_check_precedes_the_last_admin_check() -> None:
    """자기 자신 규칙이 마지막 admin 규칙보다 먼저 적용된다

    테스트 코드: US-034
    """
    # given: 자기 자신이자 마지막 admin
    target = make_user("boss", Role.ADMIN)

    # when: 강등 가능 여부를 확인한다
    with raises_with(InvalidStateError, SELF_CHANGE):
        policy.ensure_role_changeable(
            target, Role.SALES, actor_user_id=target.id, active_admin_count=1
        )
    # then: 자기 자신 문구의 상태 오류다


def test_actor_without_a_user_row_is_not_treated_as_self() -> None:
    """요청자 행이 없으면 자기 자신으로 보지 않는다"""
    # given: 요청자 id 없음
    target = make_user("kim", Role.SALES)

    # when: 역할 변경 가능 여부를 확인한다
    policy.ensure_role_changeable(target, Role.USER, actor_user_id=None, active_admin_count=2)
    # then: 예외 없이 통과한다
