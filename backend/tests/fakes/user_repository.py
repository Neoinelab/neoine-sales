"""UserRepository·LoginFailureRepository Port의 InMemory 구현(Fake).

`_items`를 유지해 FakeUnitOfWork의 롤백 스냅샷(deepcopy)에 포함된다.
"""

import copy
from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.auth.principal import Role
from app.domain.common.errors import AlreadyExistsError
from app.domain.user.errors import UserNotFoundError
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.auth.credentials import LoginId
    from app.domain.auth.login_failure import FailureCounter
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId


class FakeUserRepository(InMemoryStore["User"]):
    def __init__(self) -> None:
        super().__init__("사용자", UserNotFoundError)
        self.roster_locks = 0  # lock_roster 호출 횟수(advisory lock 대용 기록)

    async def add(self, user: User) -> None:
        if not user.is_deleted and any(
            not other.is_deleted and other.login_id == user.login_id
            for other in self._items.values()
        ):
            raise AlreadyExistsError("사용자", user.login_id.value)
        self._insert(user)

    async def get(self, user_id: UserId) -> User:
        return self._fetch(user_id, include_deleted=False)

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None:
        for user in self._items.values():
            if not user.is_deleted and user.login_id == login_id:
                return copy.deepcopy(user)
        return None

    async def list_active(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[User]:
        return self._fetch_page(offset, limit, include_deleted=False)

    async def count_active_admins(self) -> int:
        return sum(1 for u in self._items.values() if not u.is_deleted and u.role is Role.ADMIN)

    async def update(self, user: User) -> None:
        self._replace(user)

    async def lock_roster(self) -> None:
        self.roster_locks += 1


class FakeLoginFailureRepository:
    def __init__(self) -> None:
        self._items: dict[str, FailureCounter] = {}

    async def get_for_update(self, key: str) -> FailureCounter | None:
        found = self._items.get(key)
        return copy.deepcopy(found) if found else None

    async def save(self, counter: FailureCounter) -> None:
        self._items[counter.key] = copy.deepcopy(counter)

    async def delete(self, key: str) -> None:
        self._items.pop(key, None)
