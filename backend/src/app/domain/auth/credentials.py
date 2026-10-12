import re
from dataclasses import dataclass

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign

LOGIN_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
PASSWORD_MAX = 256


@dataclass(frozen=True, slots=True)
class LoginId:
    """AD 로그인 아이디. 앞뒤 공백을 지우고 소문자로 맞춘다. LDAP 특수문자는 형식에서 거부한다."""

    value: str

    def __post_init__(self) -> None:
        text = self.value.strip()
        if not text.isascii() or LOGIN_ID_PATTERN.fullmatch(text.lower()) is None:
            raise InvalidValueError(
                "로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다"
            )
        assign(self, value=text.lower())


@dataclass(frozen=True, slots=True, repr=False)
class Password:
    """비밀번호 원문 래퍼. repr/str은 마스킹하고 reveal()로만 꺼낸다. strip하지 않는다."""

    value: str

    def __post_init__(self) -> None:
        if "\x00" in self.value:
            raise InvalidValueError("비밀번호에는 NUL 문자를 쓸 수 없습니다")
        if not self.value.strip():
            raise InvalidValueError("비밀번호는 비어 있을 수 없습니다")
        if len(self.value) > PASSWORD_MAX:
            raise InvalidValueError(f"비밀번호는 {PASSWORD_MAX}자를 넘을 수 없습니다")

    def reveal(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return "Password(***)"
