from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.domain.common.business_date import start_of_business_day
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.action_type.values import ActionTypeId
    from app.domain.code.values import CodeKind
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.entities import DealAction
    from app.domain.deal_action.value_objects import DealActionId
    from app.domain.user.value_objects import UserId

KEYWORD_MAX = 100
ACTED_RANGE_REVERSED = "수행일 범위의 시작은 끝보다 늦을 수 없습니다."
DUE_RANGE_REVERSED = "Due Date 범위의 시작은 끝보다 늦을 수 없습니다."
_DATE_FIELDS = ("acted_from", "acted_to", "due_from", "due_to")


class DealActionSort(StrEnum):
    ACTED_AT_DESC = "acted_at_desc"  # 기본
    ACTED_AT_ASC = "acted_at_asc"
    DUE_DATE_ASC = "due_date_asc"


@dataclass(frozen=True, slots=True)
class DealActionQuery:
    """한 Deal의 Action 검색 조건. 모든 조건은 AND로 결합하고 페이지는 없다(전부 돌려준다).

    수행일(acted_*)과 Due Date(due_*)는 시각 없는 날짜이고 양끝을 포함한다.
    수행일은 서버 로컬 업무 날짜 기준이다(`acted_window`).
    """

    deal_code: DealCode
    action_type_id: ActionTypeId | None = None
    actor_user_id: UserId | None = None  # 수행자(users.id), 퇴사자도 조회 가능
    keyword: str | None = None  # 진행사항·Next Action·Memo에서 대소문자 구분 없이 부분 일치
    acted_from: date | None = None
    acted_to: date | None = None
    due_from: date | None = None
    due_to: date | None = None
    sort: DealActionSort = DealActionSort.ACTED_AT_DESC

    def __post_init__(self) -> None:
        for name in _DATE_FIELDS:
            if isinstance(getattr(self, name), datetime):
                raise InvalidValueError(f"{name}은(는) 시각 없는 날짜여야 합니다")
        if self.acted_from and self.acted_to and self.acted_from > self.acted_to:
            raise InvalidValueError(ACTED_RANGE_REVERSED)
        if self.due_from and self.due_to and self.due_from > self.due_to:
            raise InvalidValueError(DUE_RANGE_REVERSED)
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )

    def acted_window(self) -> tuple[datetime | None, datetime | None]:
        """수행 일시의 반개구간 [시작, 끝). 끝 날짜의 다음 날 00:00(로컬)이 끝이다."""
        start = start_of_business_day(self.acted_from) if self.acted_from else None
        end = start_of_business_day(self.acted_to + timedelta(days=1)) if self.acted_to else None
        return start, end


class DealActionRepository(Protocol):
    async def add(self, action: DealAction) -> None:
        """같은 id는 AlreadyExistsError, 소속 Deal이 없으면 DealNotFoundError.

        스냅숏의 Status·Forecast 코드가 없으면 InvalidReferenceError("Status 코드" 또는
        "Forecast 코드", identifier=key), 수행자 users 행이 없으면 InvalidReferenceError("사용자"),
        유형이 없으면 InvalidReferenceError("Action 유형", identifier=유형 id).
        """
        ...

    async def get(self, action_id: DealActionId) -> DealAction:
        """없으면 DealActionNotFoundError. content.action_type.name은 읽는 시점의 유형 이름."""
        ...

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        """조건에 맞는 Action 전부를 query.sort 순서로 돌려준다(페이지 없음).

        acted_at 정렬은 같은 시각이면 id 오름차순, due_date_asc는 같은 날이면 acted_at 내림차순.
        """
        ...

    async def update(self, action: DealAction) -> None:
        """내용(content)과 updated_at만 저장한다. 없으면 DealActionNotFoundError."""
        ...

    async def delete(self, action_id: DealActionId) -> None:
        """물리 삭제한다. 없으면 DealActionNotFoundError."""
        ...

    async def count_by_code(self, kind: CodeKind) -> Mapping[str, int]:
        """코드 key별로 스냅숏이 그 코드를 쓰는 Action 수(Status는 status_key, Forecast는
        forecast_key). 쓰는 Action이 없는 key는 빠진다."""
        ...

    async def count_by_action_type(self) -> Mapping[ActionTypeId, int]:
        """유형 id별 그 유형을 쓰는 Action 수. 쓰는 Action이 없는 유형은 빠진다."""
        ...
