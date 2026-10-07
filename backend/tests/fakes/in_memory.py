"""InMemory Fake 공통 저장소. 실제 DB처럼 복사본을 저장·반환해 update 누락을 테스트가 잡게 한다."""

import copy
from typing import TYPE_CHECKING, Any

from app.application.ports.pagination import check_page
from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import AlreadyExistsError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable


class InMemoryStore[EntityT: AuditedEntity[Any]]:
    def __init__(self, label: str, not_found: Callable[[Any], NotFoundError]) -> None:
        self._label = label
        self._not_found = not_found
        self._items: dict[Any, EntityT] = {}

    def _insert(self, entity: EntityT) -> None:
        if entity.id in self._items:
            raise AlreadyExistsError(self._label, entity.id)
        self._items[entity.id] = copy.deepcopy(entity)

    def _fetch(self, entity_id: object, *, include_deleted: bool) -> EntityT:
        item = self._items.get(entity_id)
        if item is None or (item.is_deleted and not include_deleted):
            raise self._not_found(entity_id)
        return copy.deepcopy(item)

    def _fetch_page(self, offset: int, limit: int, *, include_deleted: bool) -> list[EntityT]:
        check_page(offset, limit)
        visible = [i for i in self._items.values() if include_deleted or not i.is_deleted]
        visible.sort(key=lambda item: (item.created_at, str(item.id)))
        return [copy.deepcopy(item) for item in visible[offset : offset + limit]]

    def _replace(self, entity: EntityT) -> None:
        if entity.id not in self._items:  # 삭제된 항목도 갱신(복원)할 수 있어야 한다
            raise self._not_found(entity.id)
        self._items[entity.id] = copy.deepcopy(entity)
