"""인증 방식: 시스템 전역 하나. AD 연동(ad) 또는 앱이 계정을 직접 관리(local)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime


class AuthMode(StrEnum):
    AD = "ad"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class SetupProgress:
    storage_pending: bool = False
    admin_pending: bool = False

    @property
    def pending(self) -> bool:
        return self.storage_pending or self.admin_pending


SETUP_COMPLETE: Final = SetupProgress()


@dataclass(frozen=True, slots=True)
class AuthSettings:
    """최초 설정 1단계에서 고른 인증 방식(단일 행)."""

    mode: AuthMode
    updated_at: datetime
    progress: SetupProgress = SETUP_COMPLETE

    def __post_init__(self) -> None:
        require_aware(self.updated_at, "updated_at")


def effective_mode(stored: AuthSettings | None) -> AuthMode | None:
    """인증 설정 행이 없으면 기존 사용자와 관계없이 미선택이다."""
    return None if stored is None else stored.mode
