from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text, require_aware

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.value_objects import DealId
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import ActionType, DealActionId

KEYWORD_MAX = 100


class DealActionSort(StrEnum):
    ACTED_AT_DESC = "acted_at_desc"  # 기본
    DUE_DATE_ASC = "due_date_asc"  # 계획 일정이 없는 행은 마지막
    DUE_DATE_DESC = "due_date_desc"  # 계획 일정이 없는 행은 마지막


@dataclass(frozen=True, slots=True)
class DealActionQuery:
    """활동 검색 조건. 모든 조건은 AND로 결합하고, 기간은 [acted_from, acted_to) 반개구간이다."""

    deal_id: DealId | None = None
    action_type: ActionType | None = None
    actor: str | None = None
    keyword: str | None = None  # 진행내역·다음 진행 계획·메모에서 대소문자 구분 없이 부분 일치
    acted_from: datetime | None = None
    acted_to: datetime | None = None
    due_from: date | None = None  # 계획 일정 범위, 양끝 포함
    due_to: date | None = None
    sort: DealActionSort = DealActionSort.ACTED_AT_DESC
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
        self._check_due_range()
        object.__setattr__(self, "actor", optional_text(self.actor, "활동자", max_length=100))
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )

    def _check_due_range(self) -> None:
        for name in ("due_from", "due_to"):
            if isinstance(getattr(self, name), datetime):
                raise InvalidValueError(f"{name}은(는) 시각 없는 날짜여야 합니다")
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise InvalidValueError("계획 일정 범위의 시작은 끝보다 늦을 수 없습니다")


class DealActionRepository(Protocol):
    async def add(self, action: DealAction) -> None:
        """같은 id는 AlreadyExistsError, 소속 Deal이 없으면 DealNotFoundError."""
        ...

    async def get(self, action_id: DealActionId) -> DealAction:
        """없으면 DealActionNotFoundError."""
        ...

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        """활동을 query.sort 순서로 돌려준다.

        기본은 활동 일시 내림차순(같으면 id). due_date 정렬은 NULL을 마지막에 두고 동률은
        활동 일시 내림차순→id.
        """
        ...

    async def update(self, action: DealAction) -> None:
        """변경 사항을 저장한다. 없으면 DealActionNotFoundError."""
        ...

    async def delete(self, action_id: DealActionId) -> None:
        """물리 삭제한다. 없으면 DealActionNotFoundError."""
        ...

    async def exists_for_deal(self, deal_id: DealId) -> bool:
        """이 Deal의 활동 행이 있는지."""
        ...
