"""R1 AC1-1·1-5·1-7: User.change_role은 역할을 바꾸고 수정 시각을 갱신한다. 같은 역할은 그대로."""

import pytest

from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError
from tests.factories import NOW, later
from tests.factories_auth import make_resigned_user, make_user
from tests.support.expect import raises_with


def test_change_role_to_another_role_updates_role_and_touches() -> None:
    """다른 역할로 바꾸면 역할이 바뀌고 수정 시각이 갱신된다

    테스트 코드: US-031
    """
    # given: sales 사용자
    user = make_user("kim", Role.SALES)

    # when: 역할을 user로 바꾼다
    changed = user.change_role(Role.USER, later(60))

    # then: 바뀌었다는 결과와 새 역할·새 수정 시각이 남는다
    assert changed is True
    assert user.role is Role.USER
    assert user.updated_at == later(60)


def test_change_role_to_same_role_returns_false_without_touch() -> None:
    """같은 역할이면 아무것도 바꾸지 않고 수정 시각도 그대로다

    테스트 코드: US-037
    """
    # given: sales 사용자
    user = make_user("kim", Role.SALES)

    # when: 같은 sales로 바꾼다
    changed = user.change_role(Role.SALES, later(60))

    # then: 바뀌지 않았다는 결과이고 수정 시각이 그대로다
    assert changed is False
    assert user.role is Role.SALES
    assert user.updated_at == NOW


def test_change_role_of_resigned_user_raises_invalid_state() -> None:
    """퇴사자의 역할은 바꿀 수 없다

    테스트 코드: US-036
    """
    # given: 퇴사한 사용자
    user = make_resigned_user("kim", Role.SALES)
    before = user.updated_at

    # when: 역할을 바꾼다
    with raises_with(InvalidStateError, "이미 퇴사 처리된 사용자입니다"):
        user.change_role(Role.ADMIN, later(3600))

    # then: 상태 오류이고 역할·수정 시각이 그대로다
    assert user.role is Role.SALES
    assert user.updated_at == before


@pytest.mark.parametrize("new_role", [Role.ADMIN, Role.SALES, Role.USER])
def test_change_role_keeps_identity_fields(new_role: Role) -> None:
    """역할을 바꿔도 아이디·id·등록 시각은 그대로다"""
    # given: user 역할 사용자
    user = make_user("kim", Role.USER)
    login_id, user_id, created_at = user.login_id, user.id, user.created_at

    # when: 역할을 바꾼다
    user.change_role(new_role, later(5))

    # then: 아이디·id·등록 시각이 그대로다
    assert (user.login_id, user.id, user.created_at) == (login_id, user_id, created_at)
