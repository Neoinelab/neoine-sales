from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from app.domain.auth.principal import Role

UserId = NewType("UserId", int)

RESIGNED_SUFFIX = "(퇴사)"


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


@dataclass(frozen=True, slots=True)
class UserOption(UserRef):
    """사용자 선택 후보. UserRef에 아이디(login_id)를 더한다(동명이인 구분용)."""

    login_id: str
