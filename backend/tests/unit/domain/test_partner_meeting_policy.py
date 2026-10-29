"""미팅 기록 수정·삭제 권한(AC14): admin은 모두, sales는 본인 기록만, user는 불가."""

from typing import TYPE_CHECKING

import pytest
from app.domain.partner_meeting.policy import can_edit_meeting

from app.domain.auth.principal import Role
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

KIM = uid("kim")
PARK = uid("park")


@pytest.mark.parametrize(
    ("role", "user_id", "author_id", "allowed"),
    [
        pytest.param(Role.ADMIN, uid("boss"), KIM, True, id="admin-other-record"),
        pytest.param(Role.ADMIN, KIM, KIM, True, id="admin-own-record"),
        pytest.param(Role.SALES, KIM, KIM, True, id="sales-own-record"),
        pytest.param(Role.SALES, PARK, KIM, False, id="sales-other-record"),
        pytest.param(Role.USER, KIM, KIM, False, id="user-own-record"),
        pytest.param(Role.USER, PARK, KIM, False, id="user-other-record"),
    ],
)
def test_can_edit_meeting_allows_the_author_sales_and_admin_only(
    role: Role, user_id: UserId, author_id: UserId, allowed: bool
) -> None:
    assert can_edit_meeting(user_id, role, author_id) is allowed
