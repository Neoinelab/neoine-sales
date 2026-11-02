"""인증 방식: 시스템 전역 하나. AD 연동(ad) 또는 앱이 계정을 직접 관리(local)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime


class AuthMode(StrEnum):
    AD = "ad"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """최초 설정 1단계에서 고른 인증 방식(단일 행)."""

    mode: AuthMode
    updated_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.updated_at, "updated_at")


def effective_mode(
    stored: AuthSettings | None, *, has_admin: bool, has_directory: bool = False
) -> AuthMode | None:
    """저장값이 있으면 그 값. 없으면 admin이나 AD 설정이 있는 기존 시스템은 AD, 아니면 미선택."""
    if stored is not None:
        return stored.mode
    if has_admin or has_directory:
        return AuthMode.AD
    return None
