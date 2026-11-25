from typing import TYPE_CHECKING, Protocol

from app.domain.auth.mode import SETUP_COMPLETE, SetupProgress

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.mode import AuthMode, AuthSettings


class AuthSettingsRepository(Protocol):
    """인증 방식(단일 행)."""

    async def get(self) -> AuthSettings | None:
        """고른 적이 없으면 None."""
        ...

    async def save(
        self, mode: AuthMode, *, now: datetime, progress: SetupProgress = SETUP_COMPLETE
    ) -> AuthSettings:
        """단일 행을 만들거나 덮어쓴다. 호출자는 roster 잠금 안에서 부른다(닫힘 확인과 직렬화)."""
        ...
