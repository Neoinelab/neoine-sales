"""DealHistoryRepository Port의 InMemory 구현(Fake). 이력은 불변이라 add_many와 list만 있다.

id는 1부터 저장 순서대로 늘어난다(SQL의 identity와 같다). 목록은 changed_at 내림차순, 같으면 id
내림차순이다. 새 모델 모듈은 사용 시점에 가져온다.
"""

import copy
import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.code import DealCode
    from app.domain.deal.history import DealHistoryEntry, HistoryCategory


class FakeDealHistoryRepository:
    def __init__(self) -> None:
        self._items: dict[int, DealHistoryEntry] = {}  # UoW 스냅샷이 이 이름을 쓴다

    def remove_of_deal(self, code: DealCode) -> None:
        """Deal 삭제의 CASCADE."""
        for entry_id in [i for i, e in self._items.items() if e.deal_code == code]:
            del self._items[entry_id]

    async def add_many(self, entries: Sequence[DealHistoryEntry]) -> None:
        for entry in entries:
            new_id = max(self._items, default=0) + 1
            self._items[new_id] = dataclasses.replace(copy.deepcopy(entry), id=new_id)

    async def list(
        self,
        code: DealCode,
        *,
        category: HistoryCategory | None = None,
    ) -> Sequence[DealHistoryEntry]:
        found: list[Any] = [
            e
            for e in self._items.values()
            if e.deal_code == code and (category is None or e.draft.category == category)
        ]
        found.sort(key=lambda e: (e.changed_at, e.id), reverse=True)
        return [copy.deepcopy(e) for e in found]
