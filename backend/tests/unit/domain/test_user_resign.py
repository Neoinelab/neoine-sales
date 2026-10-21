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
    user = make_user("kim")

    user.resign(later(60))

    assert user.deleted_at == later(60)
    assert user.delete_reason is UserDeleteReason.RESIGNED
    assert not user.is_active
    assert user.updated_at == later(60)


def test_resign_accepts_an_explicit_reason() -> None:
    user = make_user("kim")

    user.resign(later(60), UserDeleteReason.RESIGNED)

    assert user.delete_reason is UserDeleteReason.RESIGNED


def test_resign_twice_is_rejected_and_keeps_the_first_time() -> None:
    user = make_user("kim")
    user.resign(later(60))

    with pytest.raises(InvalidStateError):
        user.resign(later(120))

    assert user.deleted_at == later(60)


def test_resign_requires_an_aware_time() -> None:
    user = make_user("kim")

    with pytest.raises(InvalidValueError):
        user.resign(NOW.replace(tzinfo=None))


def test_resign_keeps_identity_and_profile_for_history() -> None:
    user = make_user("kim", Role.ADMIN)
    user.record_login(later(1), display_name="김영업", email="kim@corp.test")
    original_id = user.id

    user.resign(later(60))

    assert user.id == original_id
    assert user.login_id == LoginId("kim")
    assert user.role is Role.ADMIN  # 마지막 역할은 이력 목적으로만 남는다
    assert user.display_name == "김영업"


def test_registering_the_same_login_id_again_creates_a_new_row_with_a_new_id() -> None:
    old = make_user("kim")
    old.resign(later(60))

    new = User.register(
        LoginId("kim"),
        Role.USER,
        entity_id=UserId(new_id()),
        created_by_user_id=old.created_by_user_id,
        now=later(120),
    )

    assert new.id != old.id
    assert new.is_active
    assert old.deleted_at == later(60)  # 이전 행은 그대로 퇴사 상태


@pytest.mark.parametrize("name", ["reinstate", "restore", "rehire", "reactivate", "undelete"])
def test_user_has_no_way_to_bring_a_resigned_row_back(name: str) -> None:
    user = make_user("kim")

    assert not hasattr(user, name)
    assert not hasattr(User, name)
