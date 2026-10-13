from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import DEFAULT_LIMIT, check_page
from app.domain.auth.principal import SUBJECT_MAX
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text
from app.domain.deal.value_objects import OWNER_MAX, VENDOR_MAX

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from app.domain.customer.value_objects import CustomerId
    from app.domain.deal.entities import Deal
    from app.domain.deal.pipeline import StageTotal
    from app.domain.deal.stage import DealStage
    from app.domain.deal.value_objects import DealCode, DealId
    from app.domain.partner.value_objects import PartnerId

KEYWORD_MAX = 100


def normalize_owner_user_id(value: str | None) -> str | None:
    """등록 사용자 필터 정규화: 앞뒤 공백 제거, 공백뿐이면 None(전체), 대소문자 유지."""
    return optional_text(value, "등록 사용자", max_length=SUBJECT_MAX)


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
    stage: DealStage | None = None  # 정확 일치
    owner_user_id: str | None = None  # 등록 사용자 subject, 정확 일치(대소문자 유지)
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
        object.__setattr__(self, "owner_user_id", normalize_owner_user_id(self.owner_user_id))


class DealRepository(Protocol):
    """Deal 저장소 계약. Deal Code는 전체에서 고유하다. 삭제는 물리 삭제다."""

    async def add(self, deal: Deal) -> None:
        """같은 id는 AlreadyExistsError, 같은 Deal Code는 DuplicateDealCodeError.

        참조하는 고객·파트너가 없으면(FK 경쟁 포함) InvalidReferenceError.
        """
        ...

    async def get(self, deal_id: DealId, *, for_update: bool = False) -> Deal:
        """없으면 DealNotFoundError.

        for_update=True면 트랜잭션이 끝날 때까지 이 Deal 행을 잠근다(동시 단계 변경 대비).
        """
        ...

    async def get_by_code(self, code: DealCode) -> Deal:
        """업무 키로 조회한다. 없으면 DealNotFoundError."""
        ...

    async def list(self, *, offset: int = 0, limit: int = DEFAULT_LIMIT) -> Sequence[Deal]:
        """생성 시각 오름차순. 잘못된 offset/limit은 InvalidValueError."""
        ...

    async def search(self, query: DealQuery) -> Sequence[Deal]:
        """Deal 중 조건에 맞는 것을 생성 시각 오름차순(같으면 id)으로 돌려준다."""
        ...

    async def summarize_pipeline(self, *, owner_user_id: str | None = None) -> Sequence[StageTotal]:
        """Deal을 (단계, 통화)로 묶은 건수·합계. 순서는 보장하지 않는다.

        owner_user_id를 주면 그 사용자가 등록한 Deal만 집계한다(정확 일치).
        """
        ...

    async def exists_for_customer(self, customer_id: CustomerId) -> bool:
        """이 고객을 참조하는 Deal이 있는지."""
        ...

    async def exists_for_partner(self, partner_id: PartnerId) -> bool:
        """이 파트너를 참조하는 Deal이 있는지."""
        ...

    async def update(self, deal: Deal) -> None:
        """변경 사항(단계 포함)을 저장한다.

        없으면 DealNotFoundError, 다른 Deal과 코드가 충돌하면 DuplicateDealCodeError,
        참조하는 고객·파트너가 없으면(FK 경쟁 포함) InvalidReferenceError.
        """
        ...

    async def delete(self, deal_id: DealId) -> None:
        """물리 삭제한다. 없으면 DealNotFoundError, 활동·단계 이력이 FK로 막으면 DealInUseError."""
        ...
