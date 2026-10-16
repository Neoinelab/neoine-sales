from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.code import DealCode
    from app.domain.deal.history import DealHistoryEntry, HistoryCategory


class DealHistoryRepository(Protocol):
    """Deal History 저장소. 이력은 불변이라 추가와 조회만 있다(Deal 삭제 때 함께 지워진다)."""

    async def add_many(self, entries: Sequence[DealHistoryEntry]) -> None:
        """주어진 순서대로 저장한다. id는 저장 순서대로 늘어난다."""
        ...

    async def list(
        self, code: DealCode, *, category: HistoryCategory | None = None
    ) -> Sequence[DealHistoryEntry]:
        """변경 시각 내림차순, 같으면 id 내림차순(나중에 기록한 것이 위)."""
        ...
