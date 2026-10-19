"""첨부 삭제·교체 권한(P2b AC-11·14): admin 모두, sales는 본인 + 퇴사한 sales의 파일, user 불가."""

from uuid import uuid4

import pytest

from app.domain.attachment.policy import can_delete_attachment
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserId, UserRef
from tests.support.user_ids import uid

ME = uid("me")
OTHER = uid("other")


def _uploader(user_id: UserId, role: Role, *, resigned: bool = False) -> UserRef:
    return UserRef(id=user_id, name="업로더", resigned=resigned, role=role)


@pytest.mark.parametrize(
    ("role", "uploader_is_me", "uploader_role", "uploader_resigned", "expected"),
    [
        (Role.ADMIN, False, Role.SALES, False, True),
        (Role.ADMIN, False, Role.ADMIN, False, True),
        (Role.ADMIN, False, Role.USER, True, True),
        (Role.ADMIN, True, Role.ADMIN, False, True),
        (Role.SALES, True, Role.SALES, False, True),
        (Role.SALES, False, Role.SALES, False, False),
        (Role.SALES, False, Role.ADMIN, False, False),
        (Role.SALES, False, Role.SALES, True, True),
        (Role.SALES, False, Role.ADMIN, True, False),
        (Role.SALES, False, Role.USER, True, False),
        (Role.USER, True, Role.USER, False, False),
        (Role.USER, False, Role.SALES, True, False),
    ],
)
def test_can_delete_attachment_matrix(
    role: Role,
    uploader_is_me: bool,
    uploader_role: Role,
    uploader_resigned: bool,
    expected: bool,
) -> None:
    uploader = _uploader(ME if uploader_is_me else OTHER, uploader_role, resigned=uploader_resigned)

    assert can_delete_attachment(ME, role, uploader) is expected


def test_a_user_id_that_matches_nobody_gets_the_same_answer() -> None:
    uploader = _uploader(UserId(uuid4()), Role.SALES)

    assert can_delete_attachment(UserId(uuid4()), Role.SALES, uploader) is False
