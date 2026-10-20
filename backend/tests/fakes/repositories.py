"""Repository Port의 InMemory 구현(Fake). 단위 테스트와 계약 테스트에서 사용한다.

Deal 저장소는 `tests/fakes/deals.py`(여기서 다시 내보낸다), 이력 저장소는 `deal_history.py`다.

Action 저장소(P2 모델)는 실제 DB처럼 동작한다: 소속 Deal이 없으면 DealNotFoundError,
스냅숏 key가 codes에 없으면 InvalidReferenceError(카탈로그가 시드된 경우만, FakeDealRepository와
같다), Deal 삭제는 Action을 함께 지운다(CASCADE). 검색 날짜는 `query.acted_window()` 반개구간이다.
유형은 id로 저장하고 읽을 때 현재 이름을 붙인다(`ActionTypeRef.name`). 유형이 없으면(유형 카탈로그가
시드되지 않은 Fake는 확인하지 않는다) InvalidReferenceError("Action 유형")다.
"""

import copy
from dataclasses import replace
from datetime import date
from typing import TYPE_CHECKING, Any

from app.domain.common.errors import InvalidReferenceError
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.errors import DealActionNotFoundError
from tests.fakes.deals import FakeDealRepository
from tests.fakes.in_memory import InMemoryStore

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.deal_action_repository import DealActionQuery
    from app.domain.action_type.values import ActionTypeId
    from app.domain.code.values import CodeKind
    from app.domain.deal.code import DealCode
    from app.domain.deal_action.value_objects import DealActionId

__all__ = ["FakeDealActionRepository", "FakeDealRepository"]


def _matches(action: DealAction, query: DealActionQuery) -> bool:
    content = action.content
    keyword = query.keyword.lower() if query.keyword else None
    searchable = [t for t in (content.action, content.next_action, content.memo) if t is not None]
    start, end = query.acted_window()
    due = content.due_date
    return (
        action.deal_code == query.deal_code
        and (query.action_type_id is None or content.action_type.id == query.action_type_id)
        and (query.actor_user_id is None or action.actor_user_id == query.actor_user_id)
        and (start is None or action.acted_at >= start)
        and (end is None or action.acted_at < end)
        and (query.due_from is None or (due is not None and due >= query.due_from))
        and (query.due_to is None or (due is not None and due <= query.due_to))
        and _status_matches(action, query)
        and (keyword is None or any(keyword in text.lower() for text in searchable))
    )


def _status_matches(action: DealAction, query: DealActionQuery) -> bool:
    """상태 필터가 있으면 Next Action이 없는 Action(상태 NULL)은 제외한다."""
    wanted = query.next_action_status
    if wanted is None:
        return True
    state = action.next_action_state
    return state is not None and state.status in wanted.statuses()


def _sorted(found: list[DealAction], sort: str) -> list[DealAction]:
    """acted_at 두 정렬은 동률을 id 오름차순, due_date_asc는 동률을 acted_at 내림차순으로 정한다."""
    if sort == "acted_at_asc":
        return sorted(found, key=lambda a: (a.acted_at, str(a.id)))
    by_latest = sorted(found, key=lambda a: (-a.acted_at.timestamp(), str(a.id)))
    if sort == "acted_at_desc":
        return by_latest
    # 안정 정렬: 동률은 최신순 유지. Due가 없는 행은 맨 뒤(NULLS LAST)
    return sorted(
        by_latest, key=lambda a: (a.content.due_date is None, a.content.due_date or date.max)
    )


class FakeDealActionRepository(InMemoryStore[DealAction]):
    def __init__(self) -> None:
        super().__init__("deal_action", DealActionNotFoundError)
        self._deals: Any = None
        self._codes: Any = None
        self._action_types: Any = None

    def wire(self, *, deals: Any, codes: Any = None, action_types: Any = None) -> None:  # noqa: ANN401
        """소속 Deal·스냅숏 코드·유형 존재 확인(FK 모사)과 유형 이름 읽기에 쓸 저장소를 연결한다."""
        self._deals = deals
        self._codes = codes
        self._action_types = action_types

    def _ensure_type(self, action: DealAction) -> None:
        types = self._action_types
        if types is None or not types._items:
            return  # 유형 카탈로그가 시드되지 않은 Fake는 유형을 확인하지 않는다
        ref = action.content.action_type
        if ref.id not in types._items:
            raise InvalidReferenceError("Action 유형", ref.id)

    def _named(self, action: DealAction) -> DealAction:
        """복사본의 유형 이름을 지금 이름으로 바꾼다(저장은 id만, 이름은 읽을 때 붙는다)."""
        copied = copy.deepcopy(action)
        types = self._action_types
        current = None if types is None else types._items.get(copied.content.action_type.id)
        if current is not None:
            ref = replace(copied.content.action_type, name=current.name)
            copied.content = replace(copied.content, action_type=ref)
        return copied

    def _ensure_references(self, action: DealAction) -> None:
        if self._deals is not None and action.deal_code not in self._deals._items:
            raise DealNotFoundError(action.deal_code.value)
        if self._codes is None or not self._codes._items:
            return  # 카탈로그가 시드되지 않은 Fake는 코드를 확인하지 않는다
        for kind, label, key in (
            ("status", "Status 코드", action.snapshot.status_key),
            ("forecast", "Forecast 코드", action.snapshot.forecast_key),
        ):
            known = {c.key.value for c in self._codes._items.values() if c.kind.value == kind}
            if key not in known:
                raise InvalidReferenceError(label, key)

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE."""
        for action_id in [i for i, a in self._items.items() if a.deal_code == code]:
            del self._items[action_id]

    async def add(self, action: DealAction) -> None:
        self._ensure_references(action)
        self._ensure_type(action)
        self._insert(action)

    async def get(self, action_id: DealActionId) -> DealAction:
        return self._named(self._fetch(action_id))

    async def search(self, query: DealActionQuery) -> Sequence[DealAction]:
        found = [a for a in self._items.values() if _matches(a, query)]
        return [self._named(a) for a in _sorted(found, str(query.sort))]

    async def update(self, action: DealAction) -> None:
        """content·Next Action 상태·updated_at만 저장한다(스냅숏·수행 시각·담당자는 그대로)."""
        stored = self._fetch(action.id)
        self._ensure_type(action)
        stored.content = action.content
        stored.next_action_state = action.next_action_state
        stored.updated_at = action.updated_at
        self._replace(stored)

    async def delete(self, action_id: DealActionId) -> None:
        """물리 삭제. 없으면 DealActionNotFoundError."""
        self._fetch(action_id)
        del self._items[action_id]

    async def count_by_code(self, kind: CodeKind) -> Mapping[str, int]:
        """스냅숏 key별 Action 수(Status는 status_key, Forecast는 forecast_key)."""
        counts: dict[str, int] = {}
        for action in self._items.values():
            key = (
                action.snapshot.status_key
                if kind.value == "status"
                else action.snapshot.forecast_key
            )
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def count_by_action_type(self) -> Mapping[ActionTypeId, int]:
        """유형 id별 Action 수. 쓰는 Action이 없는 유형은 빠진다."""
        counts: dict[ActionTypeId, int] = {}
        for action in self._items.values():
            type_id = action.content.action_type.id
            counts[type_id] = counts.get(type_id, 0) + 1
        return counts
