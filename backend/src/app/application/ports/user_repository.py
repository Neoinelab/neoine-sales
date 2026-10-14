from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT
from app.domain.user.value_objects import UserStatusFilter

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from app.domain.auth.credentials import LoginId
    from app.domain.user.entities import User
    from app.domain.user.value_objects import UserId, UserRef


class UserRepository(Protocol):
    """사용자 저장소. login_id 유일성은 DB가 아니라 RegisterUser가 roster 잠금 안에서 지킨다.

    퇴사한 행은 같은 login_id로 여러 개 있을 수 있으므로 login_id 조회는 재직 행만 대상이다.
    """

    async def add(self, user: User) -> None:
        """같은 id는 AlreadyExistsError. 같은 login_id(퇴사자 포함)는 막지 않는다.

        created_by_user_id가 가리키는 사용자가 없으면(자기 자신을 가리키는 최초 admin은 제외)
        UserNotFoundError(등록자 삭제 경쟁).
        """
        ...

    async def get(self, user_id: UserId) -> User:
        """퇴사자 포함. 없으면 UserNotFoundError."""
        ...

    async def get_for_update(self, user_id: UserId) -> User:
        """행을 잠그고(FOR UPDATE) 읽는다. 퇴사자 포함. 없으면 UserNotFoundError."""
        ...

    async def get_refs(self, user_ids: Collection[UserId]) -> Mapping[UserId, UserRef]:
        """표시용 참조를 한 번에 읽는다. 퇴사자 포함, 없는 id는 결과에서 빠진다."""
        ...

    async def get_active_by_login_id(self, login_id: LoginId) -> User | None:
        """재직 행만(대소문자 무시). 없으면 None.

        재직 행이 2개 이상이면(정합 위반) AmbiguousLoginIdError(건수만 담는다)를 올린다.
        퇴사자 행은 세지 않는다.
        """
        ...

    async def list_users(
        self,
        *,
        status: UserStatusFilter = UserStatusFilter.ACTIVE,
        offset: int = 0,
        limit: int = DEFAULT_LIMIT,
    ) -> Sequence[User]:
        """생성 순서. offset/limit이 범위 밖이면 InvalidValueError."""
        ...

    async def search_refs(
        self, *, keyword: str | None, include_resigned: bool, limit: int
    ) -> Sequence[UserRef]:
        """표시 이름(없으면 login_id로 대체한 name) 부분 일치(대소문자 무시) 참조를 생성 순서로.

        표시 이름이 있는 사용자는 login_id로 검색되지 않는다. limit은 check_page.
        """
        ...

    async def count_active_admins(self) -> int:
        """재직 admin 수(퇴사자 제외)."""
        ...

    async def update(self, user: User) -> None:
        """없으면 UserNotFoundError."""
        ...

    async def delete(self, user_id: UserId) -> None:
        """물리 삭제한다. 없으면 UserNotFoundError, 다른 데이터가 참조하면 UserInUseError."""
        ...

    async def has_links(self, user_id: UserId) -> bool:
        """users를 FK로 참조하는 행이 있는지(세션과 자기 자신이 등록자인 행은 제외)."""
        ...

    async def lock_assignable(self, user_id: UserId) -> bool:
        """재직 사용자면 행을 FOR KEY SHARE로 잠그고 True. 퇴사했거나 없으면 False."""
        ...

    async def lock_roster(self) -> None:
        """사용자 명단 변경(등록·삭제)을 직렬화하는 트랜잭션 수준 잠금."""
        ...
