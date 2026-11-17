"""Comment 삭제·읽음 처리 권한: 삭제는 admin 모두 / sales 본인 / user 불가, 읽음 처리는 Owner만."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.deal_comment.policy import can_delete_comment, can_mark_comments_read
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

KIM = uid("cm-kim")
PARK = uid("cm-park")


@pytest.mark.parametrize(
    ("user", "role", "allowed"),
    [
        pytest.param(KIM, Role.SALES, True, id="author-sales"),
        pytest.param(PARK, Role.SALES, False, id="other-sales"),
        pytest.param(PARK, Role.ADMIN, True, id="admin-of-someone-else"),
        pytest.param(KIM, Role.ADMIN, True, id="admin-author"),
        pytest.param(KIM, Role.USER, False, id="read-only-user-even-as-author"),
        pytest.param(PARK, Role.USER, False, id="read-only-user-other"),
    ],
)
def test_can_delete_comment_follows_the_role_rule(user: UserId, role: Role, allowed: bool) -> None:
    """삭제 권한은 admin 모두 / sales 본인 / user 불가다.

    테스트 코드: CM-025
    """
    # given: 작성자가 KIM인 Comment
    # when: 사용자·역할별로 삭제 권한을 묻는다
    result = can_delete_comment(user, role, KIM)

    # then: 규칙대로 허용·거절된다
    assert result is allowed


@pytest.mark.parametrize(
    ("user", "owner", "allowed"),
    [
        pytest.param(KIM, KIM, True, id="the-owner"),
        pytest.param(PARK, KIM, False, id="someone-else"),
        pytest.param(KIM, PARK, False, id="former-owner-after-change"),
    ],
)
def test_only_the_deals_current_owner_may_mark_comments_read(
    user: UserId, owner: UserId, allowed: bool
) -> None:
    """읽음 처리는 그 Deal의 현재 Owner만 할 수 있다(역할과 무관하게 사용자 id만 본다).

    테스트 코드: CM-050, CM-053
    """
    # given: Deal의 현재 Owner
    # when: 사용자가 읽음 처리 권한을 묻는다
    result = can_mark_comments_read(user, owner)

    # then: Owner 본인만 허용된다
    assert result is allowed
