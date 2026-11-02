import logging
from typing import TYPE_CHECKING

from app.application.auth.log_ids import short_hash
from app.domain.user.errors import AmbiguousLoginIdError

if TYPE_CHECKING:
    from app.application.ports.user_repository import UserRepository
    from app.domain.auth.credentials import LoginId
    from app.domain.user.entities import User

logger = logging.getLogger(__name__)


async def find_active_user(users: UserRepository, account: LoginId, *, purpose: str) -> User | None:
    """재직 사용자를 찾는다. 같은 아이디의 재직 행이 둘 이상이면(정합 위반) 없는 것으로 본다."""
    try:
        return await users.get_active_by_login_id(account)
    except AmbiguousLoginIdError as error:
        logger.warning(
            "재직 로그인 아이디 중복으로 %s 거부 count=%d login_id_hash=%s",
            purpose,
            error.count,
            short_hash(account.value),
        )
        return None
