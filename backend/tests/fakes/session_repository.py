"""SessionRepository Port의 InMemory 구현(Fake)."""

import copy
from typing import TYPE_CHECKING

from app.domain.common.errors import AlreadyExistsError, NotFoundError
from app.domain.user.errors import UserNotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.domain.auth.session import AuthSession
    from app.domain.user.value_objects import UserId


class FakeSessionRepository:
    def __init__(self, *, user_exists: Callable[[UserId], bool] | None = None) -> None:
        """user_exists를 주면 SQL의 users FK를 모사한다: 없는 사용자의 세션은 UserNotFoundError."""
        self._items: dict[str, AuthSession] = {}
        self.user_exists = (
            user_exists  # 테스트가 나중에 바꿔 "발급 직전 사용자 삭제"를 만들 수 있다
        )

    async def add(self, session: AuthSession, token_hash: str) -> None:
        user_id = session.principal.user_id
        if self.user_exists is not None and not self.user_exists(user_id):
            raise UserNotFoundError(user_id)
        if token_hash in self._items:
            raise AlreadyExistsError("세션", token_hash)
        self._items[token_hash] = copy.deepcopy(session)

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        found = self._items.get(token_hash)
        return copy.deepcopy(found) if found else None

    async def update(self, session: AuthSession) -> None:
        for token_hash, stored in self._items.items():
            if stored.id == session.id:
                self._items[token_hash] = copy.deepcopy(session)
                return
        raise NotFoundError("세션", session.id)

    async def delete_all_for_user(self, user_id: UserId) -> int:
        """그 사용자의 세션 행을 모두 지우고(폐기된 것 포함) 지운 개수를 돌려준다."""
        doomed = [h for h, s in self._items.items() if s.principal.user_id == user_id]
        for token_hash in doomed:
            del self._items[token_hash]
        return len(doomed)
