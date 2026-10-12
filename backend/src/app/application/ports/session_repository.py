from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.auth.session import AuthSession


class SessionRepository(Protocol):
    async def add(self, session: AuthSession, token_hash: str) -> None:
        """같은 토큰 해시는 AlreadyExistsError."""
        ...

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """없으면 None. 만료·폐기 여부는 호출한 쪽이 AuthSession.is_active로 판단한다."""
        ...

    async def update(self, session: AuthSession) -> None:
        """폐기 상태를 저장한다. 없으면 NotFoundError."""
        ...

    async def revoke_all_for_subject(self, subject: str, now: datetime) -> int:
        """subject의 아직 폐기되지 않은 세션을 모두 폐기하고 그 개수를 돌려준다."""
        ...
