from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.auth.login_failure import FailureCounter


class LoginFailureRepository(Protocol):
    async def get_for_update(self, key: str) -> FailureCounter | None:
        """카운터를 읽고 같은 트랜잭션이 끝날 때까지 그 행을 잠근다. 없으면 None."""
        ...

    async def save(self, counter: FailureCounter) -> None:
        """있으면 덮어쓰고 없으면 만든다."""
        ...

    async def delete(self, key: str) -> None:
        """없어도 오류가 아니다."""
        ...
