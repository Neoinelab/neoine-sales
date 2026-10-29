from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.password_hash import PasswordHash
    from app.domain.user.value_objects import UserId


class UserPasswordHashRepository(Protocol):
    """대체 로그인용 비밀번호 해시. 사용자 id 하나에 행 하나."""

    async def get(self, user_id: UserId) -> PasswordHash | None: ...

    async def save(self, user_id: UserId, password_hash: PasswordHash, now: datetime) -> None:
        """있으면 덮어쓰고 없으면 만든다. 사용자가 없으면 UserNotFoundError."""
        ...

    async def delete(self, user_id: UserId) -> None:
        """없어도 오류가 아니다."""
        ...
