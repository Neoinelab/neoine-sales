"""참조 대상 사용자 행을 저장소에 미리 넣는 도우미(SQL FK용. Fake에서도 같은 코드가 돈다)."""

from typing import TYPE_CHECKING

from app.domain.user.errors import UserNotFoundError
from tests.factories import NOW
from tests.factories_auth import make_user
from tests.support.user_ids import login_of

if TYPE_CHECKING:
    from datetime import datetime

    from app.application.ports.user_repository import UserRepository
    from app.domain.user.value_objects import UserId


async def ensure_users(
    users: UserRepository, *user_ids: UserId | None, now: datetime = NOW
) -> None:
    """없는 id마다 재직 사용자(login_id = login_of(id))를 만든다. 이미 있으면 건드리지 않는다."""
    for user_id in user_ids:
        if user_id is None:
            continue
        try:
            await users.get(user_id)
        except UserNotFoundError:
            await users.add(make_user(login_of(user_id), entity_id=user_id, now=now))
