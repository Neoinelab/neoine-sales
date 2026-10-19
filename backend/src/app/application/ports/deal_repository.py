from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import optional_text
from app.domain.deal.period import quarter_range

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence
    from datetime import date, datetime

    from app.domain.bant.values import BantCategory, BantLabelId
    from app.domain.contact.values import ContactId, ContactKind
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import SolutionId, VendorId

KEYWORD_MAX = 100
DEFAULT_PAGE_SIZE = 20
YEAR_MIN = 1900
YEAR_MAX = 9999


class DealSort(StrEnum):
    NAME = "name"
    REVENUE_AMOUNT = "revenue_amount"
    REVENUE_DATE = "revenue_date"
    LAST_UPDATED_AT = "last_updated_at"
    STATUS = "status"  # Status 코드의 현재 순서


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class DealQuery:
    """Deal 검색 조건. 조건은 AND로 결합하고 기간은 양끝을 포함한다.

    정렬의 동률은 항상 Deal code 오름차순이다.
    """

    keyword: str | None = None  # Deal Name·고객 회사·활성 파트너 회사·code 부분 일치(대소문자 무시)
    owner_user_id: UserId | None = None
    vendor_id: VendorId | None = None
    solution_id: SolutionId | None = None
    status_key: str | None = None
    forecast_key: str | None = None
    year: int | None = None  # Expected Close 연도(필터 확장 R3)
    quarter: int | None = None  # 1~4. 연도가 없으면 호출자가 `with_year_for`로 올해를 채운다
    revenue_from: date | None = None
    revenue_to: date | None = None
    bant_label_ids: Mapping[BantCategory, BantLabelId] = field(default_factory=dict)  # 구분별 AND
    sort: DealSort = DealSort.LAST_UPDATED_AT
    order: SortOrder = SortOrder.DESC
    offset: int = 0
    limit: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        if self.revenue_from and self.revenue_to and self.revenue_from > self.revenue_to:
            raise InvalidValueError("기간의 시작은 끝보다 늦을 수 없습니다")
        self._check_year_and_quarter()
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )

    def _check_year_and_quarter(self) -> None:
        if self.year is not None and not YEAR_MIN <= self.year <= YEAR_MAX:
            raise InvalidValueError(f"연도는 {YEAR_MIN}~{YEAR_MAX} 중에서 입력하세요.")
        if self.quarter is not None:
            quarter_range(self.year or YEAR_MIN, self.quarter)  # 1~4 밖이면 InvalidValueError

    def with_year_for(self, today: date) -> DealQuery:
        """분기만 있고 연도가 없으면 today의 연도를 채운 사본, 아니면 self."""
        if self.year is None and self.quarter is not None:
            return replace(self, year=today.year)
        return self

    def revenue_window(self) -> tuple[date | None, date | None]:
        """Expected Close의 허용 범위 (시작, 끝). 양끝 포함, None은 열린 쪽.

        연/분기 범위와 revenue_from/to의 교집합이며, 시작이 끝보다 늦으면 빈 창(오류 아님)이다.
        """
        if self.year is None and self.quarter is not None:
            raise ValueError("연도 없는 분기는 with_year_for로 연도를 채운 뒤 써야 합니다.")
        start, end = self.revenue_from, self.revenue_to
        if self.year is not None:
            year_start, year_end = quarter_range(self.year, self.quarter)
            start = year_start if start is None else max(start, year_start)
            end = year_end if end is None else min(end, year_end)
        return start, end


@dataclass(frozen=True, slots=True)
class NextActionSummary:
    """가장 최근에 수행한 Action이 정한 다음 진행 계획."""

    text: str
    due_date: date

    def __post_init__(self) -> None:
        if self.due_date is None:
            raise ValueError("다음 진행 계획에는 기한이 필요합니다.")


@dataclass(frozen=True, slots=True)
class DealListItem:
    """목록·상세의 한 행: Deal과 Action에서 파생되는 값.

    last_updated_at은 Deal 수정 시각과 가장 최근 Action 수행 시각 중 늦은 쪽이다.
    """

    deal: Deal
    next_action: NextActionSummary | None
    last_updated_at: datetime


@dataclass(frozen=True, slots=True)
class ContactReference:
    """연락처를 참조하는 Deal 한 건. 파트너 링크는 비활성도 포함한다."""

    deal_code: DealCode
    role: ContactKind


@dataclass(frozen=True, slots=True)
class DealDeletionImpact:
    history_count: int
    action_count: int
    attachment_count: int


class DealRepository(Protocol):
    """Deal 저장소 계약. 키는 Deal code이고 삭제는 물리 삭제(딸린 데이터 CASCADE)다."""

    async def add(self, deal: Deal) -> None:
        """Deal과 파트너 링크·BANT 선택을 저장한다.

        같은 code는 DuplicateDealCodeError이며 트랜잭션은 계속 쓸 수 있다. 연락처·코드·Label이
        없으면 InvalidReferenceError.
        """
        ...

    async def get(self, code: DealCode, *, for_update: bool = False) -> Deal:
        """링크·BANT 포함. 없으면 DealNotFoundError. for_update면 행을 잠근다."""
        ...

    async def exists(self, code: DealCode) -> bool: ...

    async def get_item(self, code: DealCode) -> DealListItem:
        """상세용 파생값(next_action, last_updated_at) 포함. 없으면 DealNotFoundError."""
        ...

    async def search(self, query: DealQuery) -> Sequence[DealListItem]:
        """조건에 맞는 행을 query.sort/order 순서로(동률은 code 오름차순) 페이지만큼."""
        ...

    async def count(self, query: DealQuery) -> int:
        """같은 조건의 전체 건수(페이지 무시)."""
        ...

    async def update(self, deal: Deal) -> None:
        """Deal 행, 파트너 링크(새 링크 추가·해제 시각 기록), BANT 선택을 저장한다.

        없으면 DealNotFoundError, 참조가 없으면 InvalidReferenceError.
        """
        ...

    async def touch(self, codes: Collection[DealCode], now: datetime) -> None:
        """수정 시각(updated_at)만 갱신한다. 없는 code는 건너뛴다."""
        ...

    async def delete(self, code: DealCode) -> None:
        """물리 삭제한다. 활동·이력·링크·BANT 선택이 함께 지워진다. 없으면 DealNotFoundError."""
        ...

    async def deletion_impact(self, code: DealCode) -> DealDeletionImpact:
        """삭제하면 함께 지워지는 데이터 건수. 없으면 DealNotFoundError."""
        ...

    async def references_of_contact(self, contact_id: ContactId) -> Sequence[ContactReference]:
        """연락처를 고객으로 또는 파트너(비활성 링크 포함)로 참조하는 Deal."""
        ...

    async def count_by_status(self) -> Mapping[str, int]:
        """Status key별 Deal 수. Deal이 없는 key는 빠질 수 있다."""
        ...

    async def count_by_forecast(self) -> Mapping[str, int]:
        """Forecast key별 Deal 수. Deal이 없는 key는 빠질 수 있다."""
        ...

    async def count_by_bant_label(self) -> Mapping[BantLabelId, int]:
        """Label별 Deal 수. 선택된 적 없는 Label은 빠질 수 있다."""
        ...

    async def count_by_vendor(self) -> Mapping[VendorId, int]:
        """Vendor별 Deal 수. 쓰는 Deal이 없는 Vendor는 빠질 수 있다."""
        ...

    async def count_by_solution(self) -> Mapping[SolutionId, int]:
        """Solution별 Deal 수. 쓰는 Deal이 없는 Solution은 빠질 수 있다."""
        ...

    async def count_by_contacts(self, contact_ids: Sequence[ContactId]) -> Mapping[ContactId, int]:
        """연락처별로 고객 또는 파트너 링크(비활성 포함)로 참조하는 Deal 수.

        요청한 모든 id가 키로 들어 있고(참조가 없으면 0), 한 Deal은 연락처당 1건이다.
        """
        ...
