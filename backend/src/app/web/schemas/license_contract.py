"""라이선스 계약 요청·응답 스키마. 값 검증은 도메인이 하고 길이 상한은 문서용이다.

고객사명·Vendor·제품명·파트너사·담당영업은 Deal 값을 읽어 보여 주는 읽기 전용 응답 필드이며
요청에는 없다(알 수 없는 필드는 422).
"""

from datetime import date
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import BaseModel, Field, StrictInt, model_validator

from app.application.license_contract.inputs import LicenseIssueInput
from app.application.ports.deal_repository import SortOrder
from app.application.ports.license_contract_repository import (
    DEFAULT_CONTRACT_LIMIT,
    TEXT_FILTER_MAX,
    LicenseContractQuery,
    LicenseContractSort,
)
from app.application.ports.pagination import MAX_LIMIT
from app.domain.common.errors import InvalidValueError
from app.domain.license_contract.values import (
    NOTE_MAX,
    TECH_OWNER_MAX,
    TERM_MAX,
    TERM_MIN,
    ContractFields,
    ContractStatus,
    InspectionCycle,
    LicenseTerm,
    TermUnit,
)
from app.web.schemas.common import CountedPage, RequestModel
from app.web.schemas.deal_response import NamedRefResponse
from app.web.schemas.ids import QueryId
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.ports.license_contract_repository import LicenseContractRow
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef


class LicenseContractFieldsRequest(RequestModel):
    """계약 자체 칸. 생략하면 빈 기술담당·점검주기 없음·빈 Note다."""

    tech_owner: Annotated[str, Field(max_length=TECH_OWNER_MAX)] = ""
    inspection_cycle: InspectionCycle = InspectionCycle.NONE
    note: Annotated[str, Field(description=f"{NOTE_MAX}자 이내")] = ""

    def to_fields(self) -> ContractFields:
        return ContractFields(
            tech_owner=self.tech_owner, inspection=self.inspection_cycle, note=self.note
        )


class LicenseIssueRequest(LicenseContractFieldsRequest):
    start_date: date
    end_date: date | None = None
    term_amount: Annotated[StrictInt | None, Field(ge=TERM_MIN, le=TERM_MAX)] = None
    term_unit: TermUnit | None = None

    @model_validator(mode="after")
    def validate_period(self) -> Self:
        self.to_input()
        return self

    def to_input(self) -> LicenseIssueInput:
        if (self.term_amount is None) != (self.term_unit is None):
            raise InvalidValueError("기간과 기간 단위를 함께 지정하세요.")
        return LicenseIssueInput(
            fields=self.to_fields(),
            start=self.start_date,
            end=self.end_date,
            term=None
            if self.term_amount is None or self.term_unit is None
            else LicenseTerm(amount=self.term_amount, unit=self.term_unit),
        )


class LicenseTermResponse(BaseModel):
    amount: int
    unit: TermUnit


class LicenseContractResponse(BaseModel):
    id: int
    deal_code: str
    deal_name: str
    customer: str
    vendor: NamedRefResponse | None
    product: str
    partner: str | None
    sales_owner: UserRef
    status: ContractStatus
    license_start: date | None
    license_end: date | None
    term: LicenseTermResponse | None
    tech_owner: str
    inspection_cycle: InspectionCycle
    note: str
    renewed_from_id: int | None
    ended_on: date | None
    attachment_count: int
    deal_is_won: bool
    created_by: UserRef
    updated_by: UserRef
    created_at: ServerDateTime
    updated_at: ServerDateTime

    @classmethod
    def from_row(
        cls, row: LicenseContractRow, refs: Mapping[UserId, DomainUserRef]
    ) -> LicenseContractResponse:
        contract, deal = row.contract, row.deal
        vendor = deal.vendor
        term = contract.term
        return cls(
            id=contract.id,
            deal_code=deal.deal_code.value,
            deal_name=deal.deal_name,
            customer=deal.customer,
            vendor=None if vendor is None else NamedRefResponse(id=vendor.id, name=vendor.name),
            product=deal.product,
            partner=deal.partner,
            sales_owner=ref_of(refs, deal.owner_user_id),
            status=contract.status,
            license_start=contract.license_start,
            license_end=contract.license_end,
            term=None if term is None else LicenseTermResponse(amount=term.amount, unit=term.unit),
            tech_owner=contract.fields.tech_owner,
            inspection_cycle=contract.fields.inspection,
            note=contract.fields.note,
            renewed_from_id=contract.renewed_from_id,
            ended_on=contract.ended_on,
            attachment_count=row.attachment_count,
            deal_is_won=deal.is_won,
            created_by=ref_of(refs, contract.created_by),
            updated_by=ref_of(refs, contract.updated_by),
            created_at=contract.created_at,
            updated_at=contract.updated_at,
        )


def contract_user_ids(rows: Sequence[LicenseContractRow]) -> list[UserId]:
    """응답에 나올 사용자 id(담당영업·등록자·수정자)."""
    ids: list[UserId] = []
    for row in rows:
        ids += [row.deal.owner_user_id, row.contract.created_by, row.contract.updated_by]
    return ids


LicenseContractPage = CountedPage[LicenseContractResponse]


class LicenseContractSearchParams(RequestModel):
    """목록 쿼리 파라미터. 알 수 없는 파라미터는 422다."""

    customer: Annotated[str | None, Field(max_length=TEXT_FILTER_MAX)] = None
    product: Annotated[str | None, Field(max_length=TEXT_FILTER_MAX)] = None
    vendor_id: QueryId | None = None
    owner_user_id: QueryId | None = None
    status: ContractStatus | None = None
    start_from: date | None = None
    start_to: date | None = None
    end_from: date | None = None
    end_to: date | None = None
    sort: LicenseContractSort = LicenseContractSort.LICENSE_END
    order: SortOrder = SortOrder.ASC
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_CONTRACT_LIMIT

    def to_query(self) -> LicenseContractQuery:
        return LicenseContractQuery(**self.model_dump())
