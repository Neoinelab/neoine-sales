from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from app.domain.auth.principal import Role

UserId = NewType("UserId", int)

RESIGNED_SUFFIX = "(퇴사)"


class UserDeleteReason(StrEnum):
    """사용자가 목록에서 빠진 이유. 값을 추가할 때는 DB CHECK도 이 enum에서 만든다."""

    RESIGNED = "resigned"


class UserStatusFilter(StrEnum):
    """사용자 목록 필터: 재직 / 퇴사 / 전체."""

    ACTIVE = "active"
    RESIGNED = "resigned"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class UserRef:
    """다른 항목이 가리키는 사용자의 표시용 참조. 화면에 쓰는 표기(label)는 여기서만 만든다."""

    id: UserId
    name: str  # 표시 이름. 없으면 login_id로 대체한 값(login_id 자체는 담지 않는다)
    resigned: bool
    role: Role

    @property
    def label(self) -> str:
        return f"{self.name}{RESIGNED_SUFFIX}" if self.resigned else self.name
