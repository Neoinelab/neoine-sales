"""사용자 프로필(이름·이메일·전화) 변경 입력과 규칙. PATCH 의미: UNSET은 그대로, None은 비움."""

from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal

from app.domain.auth.mode import AuthMode
from app.domain.auth.principal import NAME_MAX
from app.domain.common.contact import Email, PhoneNumber
from app.domain.common.errors import InvalidStateError
from app.domain.common.validation import optional_text, reject_nul, required_text
from app.domain.user.messages import AD_PROFILE_READONLY


class _Unset(Enum):
    UNSET = "unset"


UNSET: Final = _Unset.UNSET
type Unset = Literal[_Unset.UNSET]


@dataclass(frozen=True, slots=True)
class ProfileChanges:
    display_name: str | Unset | None = UNSET
    email: str | Unset | None = UNSET
    phone: str | Unset | None = UNSET


def normalize_name(value: str | None, *, required: bool) -> str | None:
    if required:
        return required_text(value or "", "이름", max_length=NAME_MAX)
    return optional_text(value, "표시 이름", max_length=NAME_MAX)


def normalize_email(value: str | None) -> str | None:
    """빈 값은 None. 형식이 틀리면 InvalidValueError."""
    if value is None or not value.strip():
        return None
    reject_nul(value, "이메일")
    return Email(value).value


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    reject_nul(value, "전화번호")
    return PhoneNumber(value).value


def ensure_profile_editable(changes: ProfileChanges, mode: AuthMode) -> None:
    """AD 연동에서는 이름·이메일이 AD 값이라 고칠 수 없다(전화만 가능)."""
    if mode is AuthMode.AD and (changes.display_name is not UNSET or changes.email is not UNSET):
        raise InvalidStateError(AD_PROFILE_READONLY)
