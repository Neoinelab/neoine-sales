"""AC3·4·7: 사용자 퇴사 처리(소프트 삭제)와 재등록은 새 행. 퇴사 행은 복구되지 않는다."""

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.entities import User
from app.domain.user.value_objects import UserDeleteReason, UserId
from tests.factories import NOW, later
from tests.factories_auth import make_user
from tests.support.ids import new_id


def test_resign_marks_deleted_at_and_reason() -> None:
    """퇴사 처리하면 퇴사 시각·사유가 기록되고 비활성이 된다

    테스트 코드: US-058
    """
    # given: 재직 사용자
    user = make_user("kim")

    # when: 퇴사 처리한다
    user.resign(later(60))

    # then: 퇴사 시각·사유 resigned가 있고 비활성이다
    assert user.deleted_at == later(60)
    assert user.delete_reason is UserDeleteReason.RESIGNED
    assert not user.is_active
    assert user.updated_at == later(60)


def test_resign_accepts_an_explicit_reason() -> None:
    """사유를 명시해도 퇴사 처리된다"""
    # given: 재직 사용자
    user = make_user("kim")

    # when: 사유 resigned로 퇴사 처리한다
    user.resign(later(60), UserDeleteReason.RESIGNED)

    # then: 사유가 resigned다
    assert user.delete_reason is UserDeleteReason.RESIGNED


def test_resign_twice_is_rejected_and_keeps_the_first_time() -> None:
    """이미 퇴사한 사용자를 다시 퇴사 처리하면 거절되고 첫 시각이 남는다

    테스트 코드: US-063
    """
    # given: 이미 퇴사한 사용자
    user = make_user("kim")
    user.resign(later(60))

    # when: 다시 퇴사 처리한다
    with pytest.raises(InvalidStateError):
        user.resign(later(120))

    # then: 상태 오류이고 첫 퇴사 시각이 그대로다
    assert user.deleted_at == later(60)


def test_resign_requires_an_aware_time() -> None:
    """퇴사 시각은 시간대가 있어야 한다"""
    # given: 재직 사용자
    user = make_user("kim")

    # when: 시간대 없는 시각으로 퇴사 처리한다
    with pytest.raises(InvalidValueError):
        user.resign(NOW.replace(tzinfo=None))
    # then: 입력 오류다


def test_resign_keeps_identity_and_profile_for_history() -> None:
    """퇴사 처리해도 id·아이디·역할·이름이 남는다

    테스트 코드: US-058
    """
    # given: 이름이 있는 admin 사용자
    user = make_user("kim", Role.ADMIN)
    user.record_login(later(1), display_name="김영업", email="kim@corp.test")
    original_id = user.id

    # when: 퇴사 처리한다
    user.resign(later(60))

    # then: id·아이디·역할·이름이 그대로다
    assert user.id == original_id
    assert user.login_id == LoginId("kim")
    assert user.role is Role.ADMIN  # 마지막 역할은 이력 목적으로만 남는다
    assert user.display_name == "김영업"


def test_registering_the_same_login_id_again_creates_a_new_row_with_a_new_id() -> None:
    """같은 아이디를 다시 등록하면 새 id의 새 행이고 퇴사 행은 그대로다

    테스트 코드: US-008
    """
    # given: 퇴사한 kim
    old = make_user("kim")
    old.resign(later(60))

    # when: 같은 아이디로 새로 등록한다
    new = User.register(
        LoginId("kim"),
        Role.USER,
        entity_id=UserId(new_id()),
        created_by_user_id=old.created_by_user_id,
        now=later(120),
    )

    # then: 새 행은 새 id의 재직이고 예전 행은 퇴사 상태다
    assert new.id != old.id
    assert new.is_active
    assert old.deleted_at == later(60)  # 이전 행은 그대로 퇴사 상태


@pytest.mark.parametrize("name", ["reinstate", "restore", "rehire", "reactivate", "undelete"])
def test_user_has_no_way_to_bring_a_resigned_row_back(name: str) -> None:
    """퇴사 행을 되살리는 방법이 사용자 엔티티에 없다"""
    # given: 사용자 엔티티
    user = make_user("kim")

    # when·then: 복구 메서드 이름을 찾는다 → 어떤 이름도 없다
    assert not hasattr(user, name)
    assert not hasattr(User, name)
