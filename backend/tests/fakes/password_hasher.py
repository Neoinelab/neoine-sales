"""PasswordHasher Port의 Fake. `fake$<솔트 번호>$<평문 아닌 변환>` 형식이고 호출을 기록한다.

hash는 호출마다 솔트 번호가 달라 같은 비밀번호도 결과가 다르다. verify는 stored가 None이어도
호출을 기록하고(더미 계산을 했다는 증거) False를 돌려준다.
"""

from typing import TYPE_CHECKING

from app.domain.auth.password_hash import PasswordHash

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from app.domain.auth.credentials import Password


def fake_hash_of(password: str, salt: int = 0) -> PasswordHash:
    """이 Fake가 만들 수 있는 해시(시나리오 준비용)."""
    return PasswordHash(f"fake${salt}${password[::-1].encode().hex()}")


class FakePasswordHasher:
    def __init__(self) -> None:
        self._salt = 0
        self.hash_calls = 0
        self.verify_calls: list[PasswordHash | None] = []
        # verify가 불린 시점에 열려 있던 UoW 수를 재는 함수(FakeUnitOfWork.open_units를 꽂는다)
        self.open_units_probe: Callable[[], int] | None = None
        self.open_units_at_verify: list[int] = []
        # verify 도중(계산 중) 일어나는 일을 흉내 내는 훅: 퇴사·해시 변경 등
        self.during_verify: Callable[[], Awaitable[None]] | None = None

    async def hash(self, password: Password) -> PasswordHash:
        self.hash_calls += 1
        self._salt += 1
        return fake_hash_of(password.reveal(), self._salt)

    async def verify(self, password: Password, stored: PasswordHash | None) -> bool:
        self.verify_calls.append(stored)
        if self.open_units_probe is not None:
            self.open_units_at_verify.append(self.open_units_probe())
        if self.during_verify is not None:
            await self.during_verify()
        if stored is None:
            return False
        parts = stored.encoded.split("$")
        return (
            len(parts) == 3
            and parts[0] == "fake"
            and parts[2] == (password.reveal()[::-1].encode().hex())
        )
