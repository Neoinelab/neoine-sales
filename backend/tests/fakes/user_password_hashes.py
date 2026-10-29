"""UserPasswordHashRepository Port의 InMemory 구현(Fake). 사용자 id 하나에 행 하나.

`user_exists`를 주면 SQL의 users FK를 모사한다(없는 사용자의 해시는 UserNotFoundError).
`_items`를 유지해 FakeUnitOfWork의 롤백 스냅숏에 포함된다. app 도메인 모듈은 타입 힌트로만 쓴다.
"""

from typing import TYPE_CHECKING

from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from app.domain.auth.password_hash import PasswordHash

    from app.domain.user.value_objects import UserId


class FakeUserPasswordHashRepository:
    def __init__(self, *, user_exists: Callable[[UserId], bool] | None = None) -> None:
        self._items: dict[UserId, tuple[PasswordHash, datetime]] = {}
        self.user_exists = user_exists

    async def get(self, user_id: UserId) -> PasswordHash | None:
        found = self._items.get(user_id)
        return found[0] if found else None

    async def save(self, user_id: UserId, password_hash: PasswordHash, now: datetime) -> None:
        if self.user_exists is not None and not self.user_exists(user_id):
            raise UserNotFoundError(user_id)
        self._items[user_id] = (password_hash, now)

    async def delete(self, user_id: UserId) -> None:
        self._items.pop(user_id, None)

    def saved_at(self, user_id: UserId) -> datetime | None:
        """마지막으로 저장한 시각(Port 밖 확인용)."""
        found = self._items.get(user_id)
        return found[1] if found else None
