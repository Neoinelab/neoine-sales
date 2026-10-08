from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text
from app.domain.deal.value_objects import OWNER_MAX, VENDOR_MAX

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from app.domain.customer.value_objects import CustomerId
    from app.domain.deal.entities import Deal
    from app.domain.deal.value_objects import DealCode, DealId
    from app.domain.partner.value_objects import PartnerId

KEYWORD_MAX = 100


@dataclass(frozen=True, slots=True)
class DealQuery:
    """Deal 검색 조건. 조건은 AND로 결합하고, 매출일 기간은 [from, to) 반개구간이다."""

    keyword: str | None = None  # Code·Name·Owner·Vendor·Solution에서 대소문자 구분 없이 부분 일치
    customer_id: CustomerId | None = None
    partner_id: PartnerId | None = None
    owner: str | None = None  # 정확 일치
    vendor: str | None = None  # 정확 일치
    revenue_from: date | None = None
    revenue_to: date | None = None
    offset: int = 0
    limit: int = DEFAULT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        if self.revenue_from and self.revenue_to and self.revenue_from >= self.revenue_to:
            raise InvalidValueError("매출일 기간의 시작은 끝보다 앞서야 합니다")
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )
        object.__setattr__(
            self, "owner", optional_text(self.owner, "Deal Owner", max_length=OWNER_MAX)
        )
        object.__setattr__(
            self, "vendor", optional_text(self.vendor, "Vendor", max_length=VENDOR_MAX)
        )


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

    async def search(self, query: DealQuery) -> Sequence[Deal]:
        """삭제되지 않은 Deal 중 조건에 맞는 것을 생성 시각 오름차순(같으면 id)으로 돌려준다."""
        ...

    async def has_active_for_customer(self, customer_id: CustomerId) -> bool:
        """삭제되지 않은 Deal 중 이 고객을 참조하는 것이 있는지."""
        ...

    async def has_active_for_partner(self, partner_id: PartnerId) -> bool:
        """삭제되지 않은 Deal 중 이 파트너를 참조하는 것이 있는지."""
        ...

    async def update(self, deal: Deal) -> None:
        """변경 사항을 저장한다(삭제·복원 포함).

        없으면 DealNotFoundError, 다른 Deal과 코드가 충돌하면 DuplicateDealCodeError.
        """
        ...
