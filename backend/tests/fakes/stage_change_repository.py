"""DealStageChangeRepository Port의 InMemory 구현(Fake). 이력은 불변이라 add와 search만 있다."""

import copy
from typing import TYPE_CHECKING

from app.domain.common.errors import AlreadyExistsError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.application.ports.deal_stage_change_repository import DealStageChangeQuery
    from app.domain.deal.stage import DealStageChange, DealStageChangeId


class FakeDealStageChangeRepository:
    def __init__(self) -> None:
        self._items: dict[DealStageChangeId, DealStageChange] = {}  # UoW 스냅샷이 이 이름을 쓴다

    async def add(self, change: DealStageChange) -> None:
        if change.id in self._items:
            raise AlreadyExistsError("단계 이력", change.id)
        self._items[change.id] = copy.deepcopy(change)

    async def search(self, query: DealStageChangeQuery) -> Sequence[DealStageChange]:
        found = [c for c in self._items.values() if c.deal_id == query.deal_id]
        found.sort(key=lambda c: (-c.changed_at.timestamp(), str(c.id)))
        return [copy.deepcopy(c) for c in found[query.offset : query.offset + query.limit]]
