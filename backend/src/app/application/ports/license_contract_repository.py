from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from app.application.ports.deal_repository import SortOrder
from app.application.ports.pagination import check_page
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import assign, check_date_in_bounds, optional_text

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from app.domain.deal.code import DealCode
    from app.domain.license_contract.entities import LicenseContract
    from app.domain.license_contract.values import ContractStatus, LicenseContractId
    from app.domain.user.value_objects import UserId
    from app.domain.vendor.values import VendorId

TEXT_FILTER_MAX = 200
DEFAULT_CONTRACT_LIMIT = 50
START_RANGE_REVERSED = "라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다."
END_RANGE_REVERSED = "라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다."


class LicenseContractSort(StrEnum):
    DEAL_CODE = "deal_code"
    CUSTOMER = "customer"
    VENDOR = "vendor"
    PRODUCT = "product"
    PARTNER = "partner"
    LICENSE_START = "license_start"
    LICENSE_END = "license_end"
    STATUS = "status"
    SALES_OWNER = "sales_owner"
    TECH_OWNER = "tech_owner"
    INSPECTION = "inspection"
    NOTE = "note"


def _check_range(start: date | None, end: date | None, message: str) -> None:
    for day in (start, end):
        check_date_in_bounds(day, "라이선스 날짜")
    if start is not None and end is not None and start > end:
        raise InvalidValueError(message)


@dataclass(frozen=True, slots=True)
class LicenseContractQuery:
    """계약 목록 조건(AND). 텍스트는 앞뒤 공백을 지우고 비면 None이다.

    customer·product는 Deal 값의 부분 일치다. 날짜 범위는 양끝을 포함하고, 날짜 조건이 있으면
    그 날짜가 없는 계약은 제외된다. 범위가 거꾸로면 InvalidValueError다.
    """

    customer: str | None = None
    product: str | None = None
    vendor_id: VendorId | None = None
    owner_user_id: UserId | None = None
    status: ContractStatus | None = None
    start_from: date | None = None
    start_to: date | None = None
    end_from: date | None = None
    end_to: date | None = None
    sort: LicenseContractSort = LicenseContractSort.LICENSE_END
    order: SortOrder = SortOrder.ASC
    offset: int = 0
    limit: int = DEFAULT_CONTRACT_LIMIT

    def __post_init__(self) -> None:
        check_page(self.offset, self.limit)
        assign(
            self,
            customer=optional_text(self.customer, "고객사명", max_length=TEXT_FILTER_MAX),
            product=optional_text(self.product, "제품명", max_length=TEXT_FILTER_MAX),
        )
        _check_range(self.start_from, self.start_to, START_RANGE_REVERSED)
        _check_range(self.end_from, self.end_to, END_RANGE_REVERSED)


@dataclass(frozen=True, slots=True)
class VendorRef:
    id: VendorId
    name: str


@dataclass(frozen=True, slots=True)
class DealSide:
    """계약 행에 보여 줄 Deal 값(읽기 전용, 계약에는 저장하지 않는다)."""

    deal_code: DealCode
    deal_name: str
    customer: str
    vendor: VendorRef | None
    product: str
    partner: str | None
    owner_user_id: UserId
    is_won: bool  # Deal Forecast가 won


@dataclass(frozen=True, slots=True)
class LicenseContractRow:
    contract: LicenseContract
    deal: DealSide
    attachment_count: int


class LicenseContractRepository(Protocol):
    """라이선스 계약 저장소. 삭제는 물리 삭제이고 첨부 행이 함께 지워진다."""

    async def add(self, contract: LicenseContract) -> None:
        """없는 Deal은 DealNotFoundError, 사용자 없음은 InvalidReferenceError("사용자"),
        발급 상태가 한 Deal에 둘이 되면 LicenseAlreadyIssuedError.

        실패해도 같은 트랜잭션을 계속 쓸 수 있어야 한다.
        """
        ...

    async def get(
        self, contract_id: LicenseContractId, *, for_update: bool = False
    ) -> LicenseContract:
        """deal_code 포함. 없으면 LicenseContractNotFoundError. for_update면 행을 잠근다."""
        ...

    async def get_row(self, contract_id: LicenseContractId) -> LicenseContractRow:
        """Deal 값과 첨부 수를 함께. 없으면 LicenseContractNotFoundError."""
        ...

    async def update(self, contract: LicenseContract) -> None:
        """status·기간·fields·ended_at·updated_*만 저장한다. 발급 상태가 둘이 되면
        LicenseAlreadyIssuedError, 없으면 LicenseContractNotFoundError."""
        ...

    async def delete(self, contract_id: LicenseContractId) -> None:
        """물리 삭제(첨부 행 CASCADE). 없으면 LicenseContractNotFoundError."""
        ...

    async def count_of_deal(self, deal_code: DealCode) -> int:
        """그 Deal의 계약 수(종료 포함)."""
        ...

    async def delete_of_deal(self, deal_code: DealCode) -> int:
        """그 Deal의 계약을 모두 지우고(첨부 행 CASCADE) 지운 건수를 돌려준다."""
        ...

    async def ids_of_deal(self, deal_code: DealCode) -> Sequence[LicenseContractId]:
        """그 Deal의 계약 id(종료 포함, 오름차순). 지울 파일 폴더를 정하는 데 쓴다."""
        ...

    async def issued_of_deal(self, deal_code: DealCode) -> LicenseContract | None:
        """그 Deal의 발급 상태(issued_new·issued_renewal) 계약. 없으면 None."""
        ...

    async def search(self, query: LicenseContractQuery) -> Sequence[LicenseContractRow]:
        """조건(AND)에 맞는 한 페이지.

        텍스트는 대소문자 무시 부분 일치이고 `%`·`_`·`\\`는 글자 그대로다. 정렬은 주 키를
        방향대로(텍스트는 lower(...) COLLATE "C", status는 not_issued<issued_new<issued_renewal
        <ended, inspection은 monthly<quarterly<semiannual<yearly<none, sales_owner는 Owner 표시
        이름(없으면 login_id, 퇴사자 포함)), 값 없는 칸은 방향과 무관하게 맨 뒤, 동률은 id 오름차순.
        """
        ...

    async def count(self, query: LicenseContractQuery) -> int:
        """페이지와 무관한 조건에 맞는 전체 건수."""
        ...
