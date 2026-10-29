from dataclasses import dataclass

from app.domain.common.errors import InvalidValueError

PASSWORD_HASH_MAX = 512


@dataclass(frozen=True, slots=True, repr=False)
class PasswordHash:
    """저장된 비밀번호 해시의 인코딩 문자열. 형식 해석은 해시 구현(infra)이 한다.

    빈 값·NUL·512자 초과는 거절한다. repr/str에 값이 나오지 않는다.
    """

    encoded: str

    def __post_init__(self) -> None:
        if not self.encoded or "\x00" in self.encoded:
            raise InvalidValueError("password_hash는 비어 있거나 NUL을 담을 수 없습니다")
        if len(self.encoded) > PASSWORD_HASH_MAX:
            raise InvalidValueError(f"password_hash는 {PASSWORD_HASH_MAX}자를 넘을 수 없습니다")

    def __repr__(self) -> str:
        return "PasswordHash(***)"
