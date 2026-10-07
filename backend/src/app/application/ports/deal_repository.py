from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.deal.entities import Deal
    from app.domain.deal.value_objects import DealCode, DealId


class DealRepository(Protocol):
    """Deal 저장소 계약. Deal Code는 삭제된 Deal을 포함한 전체에서 고유하다."""

    async def add(self, deal: Deal) -> None:
        """같은 id는 AlreadyExistsError, 같은 Deal Code는 DuplicateDealCodeError."""
        ...

    async def get(self, deal_id: DealId, *, include_deleted: bool = False) -> Deal:
        """없거나(삭제 제외 시) 삭제된 Deal이면 DealNotFoundError."""
        ...

    async def get_by_code(self, code: DealCode, *, include_deleted: bool = False) -> Deal:
        """업무 키로 조회한다. 없으면 DealNotFoundError."""
        ...

    async def list(
        self, *, offset: int = 0, limit: int = DEFAULT_LIMIT, include_deleted: bool = False
    ) -> Sequence[Deal]:
        """생성 시각 오름차순. 잘못된 offset/limit은 InvalidValueError."""
        ...

    async def update(self, deal: Deal) -> None:
        """변경 사항을 저장한다(삭제·복원 포함).

        없으면 DealNotFoundError, 다른 Deal과 코드가 충돌하면 DuplicateDealCodeError.
        """
        ...
