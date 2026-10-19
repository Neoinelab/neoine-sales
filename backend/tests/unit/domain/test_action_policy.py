"""Action 수정·삭제 권한 규칙(Q8, R-17): admin은 모두, sales는 본인 Action만, user는 불가."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from app.domain.deal_action.policy import can_edit_action
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from app.domain.user.value_objects import UserId

KIM = uid("kim")
PARK = uid("park")


@pytest.mark.parametrize(
    ("role", "user_id", "action_actor_id", "allowed"),
    [
        pytest.param(Role.ADMIN, uid("boss"), KIM, True, id="admin-other-action"),
        pytest.param(Role.ADMIN, KIM, KIM, True, id="admin-own-action"),
        pytest.param(Role.SALES, KIM, KIM, True, id="sales-own-action"),
        pytest.param(Role.SALES, PARK, KIM, False, id="sales-other-action"),
        pytest.param(Role.USER, KIM, KIM, False, id="user-own-action"),
        pytest.param(Role.USER, PARK, KIM, False, id="user-other-action"),
    ],
)
def test_can_edit_action_allows_owner_sales_and_admin_only(
    role: Role, user_id: UserId, action_actor_id: UserId, allowed: bool
) -> None:
    assert can_edit_action(user_id, role, action_actor_id) is allowed
