"""첨부 삭제·교체 권한: admin 모두, sales는 본인 + 퇴사한 sales의 파일, user 불가."""

import pytest

from app.domain.attachment.policy import can_delete_attachment
from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserId, UserRef
from tests.support.ids import new_id
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
    """삭제 권한 표: admin은 모두, sales는 본인·퇴사 sales 파일, user는 불가.

    테스트 코드: AT-037
    """
    # given: 역할과 퇴사 여부가 정해진 업로더
    uploader = _uploader(ME if uploader_is_me else OTHER, uploader_role, resigned=uploader_resigned)

    # when: 요청자의 삭제 가능 여부를 판단한다
    allowed = can_delete_attachment(ME, role, uploader)

    # then: 기대 값과 같다
    assert allowed is expected


def test_a_user_id_that_matches_nobody_gets_the_same_answer() -> None:
    """업로더와 무관한 sales는 다른 재직 sales 파일을 지울 수 없다.

    테스트 코드: AT-037
    """
    # given: 재직 sales 업로더
    uploader = _uploader(UserId(new_id()), Role.SALES)

    # when: 업로더와 무관한 sales의 삭제 가능 여부를 판단한다
    allowed = can_delete_attachment(UserId(new_id()), Role.SALES, uploader)

    # then: 삭제할 수 없다
    assert allowed is False
