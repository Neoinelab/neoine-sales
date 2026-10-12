from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.auth.credentials import LoginId
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId


class UserRepository(Protocol):
    async def add(self, user: User) -> None:
        """같은 login_id의 활성 사용자가 있으면 AlreadyExistsError."""
        ...

    async def get(self, user_id: UserId) -> User:
        """삭제되지 않은 사용자. 없으면 UserNotFoundError."""
        ...

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None: ...

    async def list_active(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[User]:
        """생성 순서. offset/limit이 범위 밖이면 InvalidValueError."""
        ...

    async def count_active_admins(self) -> int: ...

    async def update(self, user: User) -> None:
        """없으면 UserNotFoundError."""
        ...

    async def lock_roster(self) -> None:
        """사용자 명단 변경(최초 admin 등록·삭제)을 직렬화하는 트랜잭션 수준 잠금."""
        ...
