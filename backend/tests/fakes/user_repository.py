"""UserRepository·LoginFailureRepository Port의 InMemory 구현(Fake).

`_items`를 유지해 FakeUnitOfWork의 롤백 스냅샷(deepcopy)에 포함된다.

login_id 중복은 DB가 아니라 응용 로직(RegisterUser의 재직자 조회)이 막는다. 그래서 `add`는
같은 id만 거부하고, 같은 login_id 행(퇴사자 포함)은 얼마든지 넣을 수 있다(SQL 구현도 같다).
"""

import copy
from typing import TYPE_CHECKING

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.user.errors import UserInUseError, UserNotFoundError
from app.domain.user.value_objects import UserStatusFilter
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping, Sequence

    from app.domain.auth.credentials import LoginId
    from app.domain.auth.login_failure import FailureCounter
    from app.domain.auth.principal import Role
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId, UserRef


def _matches_status(user: User, status: UserStatusFilter) -> bool:
    if status is UserStatusFilter.ALL:
        return True
    return user.is_active is (status is UserStatusFilter.ACTIVE)


class FakeUserRepository(InMemoryStore["User"]):
    def __init__(self) -> None:
        super().__init__("사용자", UserNotFoundError)
        self._referrers: list[Callable[[UserId], bool]] = []
        # True면 없는 사용자(자기 자신 제외)를 created_by로 가리키는 add를 거부한다(SQL FK 모사)
        self.enforce_creator_fk = False

    def add_referrer(self, referrer: Callable[[UserId], bool]) -> None:
        """users를 FK로 참조하는 다른 저장소를 등록한다(has_links·물리 삭제 RESTRICT 모사)."""
        self._referrers.append(referrer)

    async def add(self, user: User) -> None:
        creator = user.created_by_user_id
        if self.enforce_creator_fk and creator != user.id and creator not in self._items:
            raise UserNotFoundError(creator)
        self._insert(user)  # 같은 id만 AlreadyExistsError

    async def get(self, user_id: UserId) -> User:
        return self._fetch(user_id)

    async def get_for_update(self, user_id: UserId) -> User:
        return self._fetch(user_id)

    async def get_refs(self, user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        return {uid: self._items[uid].to_ref() for uid in set(user_ids) if uid in self._items}

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None:
        found = [u for u in self._items.values() if u.is_active and u.login_id == login_id]
        if len(found) > 1:  # 정합 위반: 재직 행이 둘 이상. SQL 구현과 같은 오류 계약
            # 오류가 구현되기 전에도 다른 테스트의 수집이 깨지지 않도록 사용 시점에 가져온다
            from app.domain.user.errors import AmbiguousLoginIdError  # noqa: PLC0415

            raise AmbiguousLoginIdError(len(found))
        return copy.deepcopy(found[0]) if found else None

    async def list_users(
        self,
        *,
        status: UserStatusFilter = UserStatusFilter.ACTIVE,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> Sequence[User]:
        check_page(offset, limit)
        found = [u for u in self._items.values() if _matches_status(u, status)]
        found.sort(key=lambda u: (u.created_at, str(u.id)))
        return [copy.deepcopy(u) for u in found[offset : offset + limit]]

    async def search_refs(
        self,
        *,
        keyword: str | None,
        include_resigned: bool,
        role: Role | None = None,
        limit: int | None = None,
    ) -> Sequence[UserRef]:
        if limit is not None:
            check_page(0, limit)
        needle = keyword.lower() if keyword else None
        found = [
            u
            for u in self._items.values()
            if (include_resigned or u.is_active)
            and (role is None or u.role is role)
            and (needle is None or needle in u.to_ref().name.lower())  # 표시 이름(없으면 아이디)만
        ]
        found.sort(key=lambda u: (u.created_at, str(u.id)))
        chosen = found if limit is None else found[:limit]
        return [u.to_ref() for u in chosen]

    def names_of(self, user_id: UserId) -> list[str]:
        """키워드 검색용 이름 후보(표시 이름, 로그인 아이디). Deal Fake의 조인 대용."""
        user = self._items.get(user_id)
        if user is None:
            return []
        return [n for n in (user.display_name, user.login_id.value) if n]

    async def count_active_admins(self) -> int:
        return sum(1 for u in self._items.values() if u.is_active and u.role.value == "admin")

    async def update(self, user: User) -> None:
        self._replace(user)

    async def has_links(self, user_id: UserId) -> bool:
        return self._linked(user_id)

    def _linked(self, user_id: UserId) -> bool:
        if any(
            other.created_by_user_id == user_id and other.id != user_id
            for other in self._items.values()
        ):
            return True
        return any(referrer(user_id) for referrer in self._referrers)

    async def lock_assignable(self, user_id: UserId) -> bool:
        user = self._items.get(user_id)
        return user is not None and user.is_active

    async def delete(self, user_id: UserId) -> None:
        self._fetch(user_id)
        if self._linked(user_id):
            raise UserInUseError(user_id)  # FK RESTRICT 모사
        self._remove(user_id)

    async def lock_roster(self) -> None:
        """단일 스레드 Fake에는 경쟁이 없어 잠금 자체는 없다."""


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
