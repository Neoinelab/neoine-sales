from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.stage import DealStageChange
    from app.domain.deal.value_objects import DealId


@dataclass(frozen=True, slots=True)
class DealStageChangeQuery:
    """한 딜의 단계 변경 이력 조회 조건."""

    deal_id: DealId
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)


class DealStageChangeRepository(Protocol):
    """단계 변경 이력 저장소. 이력은 불변이라 추가와 조회만 있다."""

    async def add(self, change: DealStageChange) -> None:
        """같은 id는 AlreadyExistsError."""
        ...

    async def search(self, query: DealStageChangeQuery) -> Sequence[DealStageChange]:
        """그 딜의 이력을 변경 시각 내림차순(같으면 id 오름차순)으로 돌려준다."""
        ...
