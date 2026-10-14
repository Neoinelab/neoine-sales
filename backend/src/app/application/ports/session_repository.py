from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.auth.session import AuthSession
    from app.domain.user.value_objects import UserId


class SessionRepository(Protocol):
    async def add(self, session: AuthSession, token_hash: str) -> None:
        """같은 토큰 해시는 AlreadyExistsError. 세션 주인(user_id)이 없으면 UserNotFoundError."""
        ...

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        """없으면 None. 만료·폐기 여부는 호출한 쪽이 AuthSession.is_active로 판단한다."""
        ...

    async def update(self, session: AuthSession) -> None:
        """폐기 상태를 저장한다. 없으면 NotFoundError."""
        ...

    async def delete_all_for_user(self, user_id: UserId) -> int:
        """그 사용자의 세션 행을 모두 지우고(폐기된 것 포함) 지운 개수를 돌려준다.

        폐기만 하면 users 행을 FK가 막아 물리 삭제할 수 없으므로 행을 지운다.
        """
        ...
