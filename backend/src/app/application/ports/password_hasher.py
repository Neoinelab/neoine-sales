from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.auth.credentials import Password
    from app.domain.auth.password_hash import PasswordHash


class PasswordHasher(Protocol):
    async def hash(self, password: Password) -> PasswordHash:
        """새 무작위 솔트로 해시한다. 같은 비밀번호도 호출마다 결과가 다르다."""
        ...

    async def verify(self, password: Password, stored: PasswordHash | None) -> bool:
        """일치하면 True.

        stored가 None이면 같은 비용의 더미 계산 뒤 False(해시 유무가 시간으로 드러나지 않게).
        형식이 깨졌거나 허용 범위 밖이면 예외 없이 False.
        """
        ...
