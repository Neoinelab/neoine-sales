from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text, require_aware

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from app.domain.deal.value_objects import DealId
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import ActionType, DealActionId

KEYWORD_MAX = 100


@dataclass(frozen=True, slots=True)
class DealActionQuery:
    """활동 검색 조건. 모든 조건은 AND로 결합하고, 기간은 [acted_from, acted_to) 반개구간이다."""

    deal_id: DealId | None = None
    action_type: ActionType | None = None
    actor: str | None = None
    keyword: str | None = None  # 제목·내용에서 대소문자 구분 없이 부분 일치
    acted_from: datetime | None = None
    acted_to: datetime | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        for name in ("acted_from", "acted_to"):
            value = getattr(self, name)
            if value is not None:
                require_aware(value, name)
        if self.acted_from and self.acted_to and self.acted_from >= self.acted_to:
            raise InvalidValueError("조회 기간의 시작은 끝보다 앞서야 합니다")
        object.__setattr__(self, "actor", optional_text(self.actor, "활동자", max_length=100))
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )


class DealActionRepository(Protocol):
    async def add(self, action: DealAction) -> None:
        """같은 id는 AlreadyExistsError."""
        ...

    async def get(self, action_id: DealActionId, *, include_deleted: bool = False) -> DealAction:
        """없거나(삭제 제외 시) 삭제된 활동이면 DealActionNotFoundError."""
        ...

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        """삭제되지 않은 활동을 활동 일시 내림차순(같으면 id)으로 돌려준다."""
        ...

    async def update(self, action: DealAction) -> None:
        """변경 사항을 저장한다(삭제 포함). 없으면 DealActionNotFoundError."""
        ...
