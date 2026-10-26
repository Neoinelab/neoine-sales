from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.application.ports.pagination import check_page
from app.domain.common.business_date import start_of_business_day
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import check_date_in_bounds, optional_text
from app.domain.deal.period import QUARTER_MONTH_EXCLUSIVE, month_range, quarter_range
from app.domain.deal.values import SOLUTION_MAX

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from app.application.ports.deal_action_repository import NextActionStatusFilter
    from app.application.ports.deal_outcome_filter import ForecastOutcomeFilter
    from app.domain.bant.values import BantLabelId
    from app.domain.contact.values import ContactId, ContactKind
    from app.domain.deal.code import DealCode
    from app.domain.deal.entities import Deal
    from app.domain.deal.risk import RiskBasis
    from app.domain.deal_action.next_action_status import NextActionStatus
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import VendorId

KEYWORD_MAX = 100
DEFAULT_PAGE_SIZE = 20
YEAR_MIN = 1900
YEAR_MAX = 9999
UPDATED_RANGE_REVERSED = "최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다"


class DealSort(StrEnum):
    NAME = "name"
    REVENUE_AMOUNT = "revenue_amount"
    REVENUE_DATE = "revenue_date"
    LAST_UPDATED_AT = "last_updated_at"
    STATUS = "status"  # Status 코드의 현재 순서
    OWNER = "owner"  # 담당자 표시 이름(없으면 login_id), 소문자
    CUSTOMER = "customer"  # 고객 회사명, 소문자
    PARTNER = "partner"  # 활성 파트너 회사명. 없으면 방향과 무관하게 맨 뒤
    VENDOR = "vendor"  # Vendor 이름. 없으면 방향과 무관하게 맨 뒤
    FORECAST = "forecast"  # Forecast 코드의 현재 순서


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


@dataclass(frozen=True, slots=True)
class DealQuery:
    """Deal 검색 조건. 조건은 AND로 결합하고 기간은 양끝을 포함한다.

    최종 업데이트 기간(updated_*)은 서버 업무 날짜 기준이다(`updated_window`).

    정렬의 동률은 항상 Deal code 오름차순이다.
    """

    keyword: str | None = None  # Deal Name·고객 회사·활성 파트너 회사·code 부분 일치(대소문자 무시)
    owner_user_id: UserId | None = None
    vendor_id: VendorId | None = None
    solution: str | None = None  # Solution 텍스트 부분 일치(대소문자 무시)
    status_key: str | None = None
    forecast_keys: frozenset[str] | None = None  # 이 중 하나와 일치(OR). None이면 조건 없음
    forecast_outcome: ForecastOutcomeFilter | None = None  # 코드 outcome 기준. forecast_keys와 AND
    year: int | None = None  # Expected Close 연도(필터 확장 R3)
    quarter: int | None = None  # 1~4. 연도가 없으면 호출자가 `with_year_for`로 올해를 채운다
    month: int | None = None  # 1~12. quarter와 함께 쓸 수 없고, 연도가 없으면 올해를 채운다
    updated_from: date | None = None  # 최종 업데이트(last_updated_at) 기간, 서버 업무 날짜
    updated_to: date | None = None
    next_action_status: NextActionStatusFilter | None = (
        None  # 기준 행(Next Action 있는 최근 행)의 상태
    )
    overdue: bool = False  # 기한초과 Deal만(stale와 함께면 OR). Won·Lost 제외
    stale: bool = False  # 미업데이트 Deal만
    risk_basis: RiskBasis | None = None  # overdue/stale 판정 기준(`with_risk_basis`로 채운다)
    sort: DealSort = DealSort.LAST_UPDATED_AT
    order: SortOrder = SortOrder.DESC
    offset: int = 0
    limit: int = DEFAULT_PAGE_SIZE

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        if self.forecast_keys is not None and not self.forecast_keys:
            raise ValueError("forecast_keys가 비었습니다. 조건이 없으면 None을 쓰세요.")
        for name in ("updated_from", "updated_to"):
            if isinstance(getattr(self, name), datetime):
                raise InvalidValueError(f"{name}은(는) 시각 없는 날짜여야 합니다")
        check_date_in_bounds(self.updated_from, "updated_from")
        check_date_in_bounds(self.updated_to, "updated_to")
        if self.updated_from and self.updated_to and self.updated_from > self.updated_to:
            raise InvalidValueError(UPDATED_RANGE_REVERSED)
        self._check_year_and_quarter()
        object.__setattr__(
            self, "keyword", optional_text(self.keyword, "검색어", max_length=KEYWORD_MAX)
        )
        object.__setattr__(
            self, "solution", optional_text(self.solution, "Solution", max_length=SOLUTION_MAX)
        )

    def _check_year_and_quarter(self) -> None:
        if self.year is not None and not YEAR_MIN <= self.year <= YEAR_MAX:
            raise InvalidValueError(f"연도는 {YEAR_MIN}~{YEAR_MAX} 중에서 입력하세요.")
        if self.quarter is not None and self.month is not None:
            raise InvalidValueError(QUARTER_MONTH_EXCLUSIVE)
        if self.quarter is not None:
            quarter_range(self.year or YEAR_MIN, self.quarter)  # 1~4 밖이면 InvalidValueError
        if self.month is not None:
            month_range(self.year or YEAR_MIN, self.month)  # 1~12 밖이면 InvalidValueError

    def wants_risk(self) -> bool:
        return self.overdue or self.stale

    def with_risk_basis(self, basis: RiskBasis) -> DealQuery:
        """위험 필터가 있으면 basis를 채운 사본, 없으면 self.

        저장소 계약: `wants_risk()`인데 `risk_basis`가 None이면 저장소는 ValueError를 낸다.
        """
        return replace(self, risk_basis=basis) if self.wants_risk() else self

    def with_year_for(self, today: date) -> DealQuery:
        """분기·월만 있고 연도가 없으면 today의 연도를 채운 사본, 아니면 self."""
        if self.year is None and (self.quarter is not None or self.month is not None):
            return replace(self, year=today.year)
        return self

    def revenue_window(self) -> tuple[date | None, date | None]:
        """Expected Close의 허용 범위 (시작, 끝). 연/분기 범위이며 양끝 포함, None은 열린 쪽."""
        if self.year is None and (self.quarter is not None or self.month is not None):
            raise ValueError("연도 없는 분기·월은 with_year_for로 연도를 채운 뒤 써야 합니다.")
        if self.year is None:
            return None, None
        if self.month is not None:
            return month_range(self.year, self.month)
        return quarter_range(self.year, self.quarter)

    def updated_window(self) -> tuple[datetime | None, datetime | None]:
        """last_updated_at의 반개구간 [시작, 끝). 끝 날짜의 다음 날 00:00(로컬)이 끝이다."""
        start = start_of_business_day(self.updated_from) if self.updated_from else None
        end = (
            start_of_business_day(self.updated_to + timedelta(days=1)) if self.updated_to else None
        )
        return start, end


@dataclass(frozen=True, slots=True)
class NextActionSummary:
    """Next Action이 있는 가장 최근 Action(기준 행)이 정한 다음 진행 계획과 그 상태."""

    text: str
    due_date: date
    status: NextActionStatus

    def __post_init__(self) -> None:
        if self.due_date is None:
            raise ValueError("다음 진행 계획에는 기한이 필요합니다.")


@dataclass(frozen=True, slots=True)
class DealListItem:
    """목록·상세의 한 행: Deal과 Action에서 파생되는 값.

    last_updated_at은 이 Deal의 모든 Action 중 가장 최근 수행 시각이고, Action이 없으면 Deal
    등록 시각이다. Deal 수정 시각은 쓰지 않는다.
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

    async def count_by_contacts(self, contact_ids: Sequence[ContactId]) -> Mapping[ContactId, int]:
        """연락처별로 고객 또는 파트너 링크(비활성 포함)로 참조하는 Deal 수.

        요청한 모든 id가 키로 들어 있고(참조가 없으면 0), 한 Deal은 연락처당 1건이다.
        """
        ...
