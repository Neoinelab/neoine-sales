"""라이선스 계약 ORM 행 <-> 도메인 엔티티 변환과 제약 이름 -> 도메인 오류 매핑."""

from typing import TYPE_CHECKING

from app.application.ports.license_contract_repository import (
    DealSide,
    VendorRef,
)
from app.application.ports.license_contract_repository import (
    LicenseContractRow as ContractRowView,
)
from app.domain.common.errors import AlreadyExistsError, InvalidReferenceError
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.license_contract.entities import LicenseContract
from app.domain.license_contract.errors import LicenseAlreadyIssuedError
from app.domain.license_contract.values import (
    ContractFields,
    ContractStatus,
    InspectionCycle,
    LicenseContractId,
    LicenseTerm,
    TermUnit,
)
from app.domain.user.value_objects import UserId
from app.domain.vendor.values import VendorId
from app.infra.db.models_license_contract import LicenseContractRow

if TYPE_CHECKING:
    from sqlalchemy import Row

    from app.infra.db.base_repository import ConstraintErrors

ISSUED_UNIQUE = "uq_license_contracts_deal_id_issued"


def to_entity(row: LicenseContractRow, deal_code: str) -> LicenseContract:
    term = (
        None
        if row.term_amount is None or row.term_unit is None
        else LicenseTerm(row.term_amount, TermUnit(row.term_unit))
    )
    return LicenseContract(
        id=LicenseContractId(row.id),
        deal_code=DealCode(deal_code),
        status=ContractStatus(row.status),
        term=term,
        license_start=row.license_start,
        license_end=row.license_end,
        fields=ContractFields(row.tech_owner, InspectionCycle(row.inspection_cycle), row.note),
        renewed_from_id=None
        if row.renewed_from_id is None
        else LicenseContractId(row.renewed_from_id),
        ended_on=row.ended_on,
        created_by=UserId(row.created_by_user_id),
        updated_by=UserId(row.updated_by_user_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def apply_changes(row: LicenseContractRow, contract: LicenseContract) -> None:
    """update가 저장하는 칸(status·기간·fields·ended_on·updated_*)만 옮긴다."""
    term = contract.term
    row.status = contract.status.value
    row.license_start = contract.license_start
    row.license_end = contract.license_end
    row.term_amount = None if term is None else term.amount
    row.term_unit = None if term is None else term.unit.value
    row.tech_owner = contract.fields.tech_owner
    row.inspection_cycle = contract.fields.inspection.value
    row.note = contract.fields.note
    row.ended_on = contract.ended_on
    row.updated_by_user_id = contract.updated_by
    row.updated_at = contract.updated_at


def new_row(contract: LicenseContract, deal_id: int) -> LicenseContractRow:
    row = LicenseContractRow(
        id=contract.id,
        deal_id=deal_id,
        renewed_from_id=contract.renewed_from_id,
        created_by_user_id=contract.created_by,
        created_at=contract.created_at,
    )
    apply_changes(row, contract)
    return row


def write_errors(contract: LicenseContract) -> ConstraintErrors:
    return {
        ISSUED_UNIQUE: LicenseAlreadyIssuedError,
        "fk_license_contracts_deal_id_deals": lambda: DealNotFoundError(contract.deal_code.value),
        "fk_license_contracts_created_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", contract.created_by
        ),
        "fk_license_contracts_updated_by_user_id_users": lambda: InvalidReferenceError(
            "사용자", contract.updated_by
        ),
        "pk_license_contracts": lambda: AlreadyExistsError("라이선스 계약", contract.id),
    }


def to_view(found: Row[tuple[object, ...]]) -> ContractRowView:
    """`license_contract_query.row_select()`의 한 행을 목록 행으로 바꾼다."""
    vendor = (
        None if found.vendor_id is None else VendorRef(VendorId(found.vendor_id), found.vendor_name)
    )
    return ContractRowView(
        contract=to_entity(found.LicenseContractRow, found.deal_code),
        deal=DealSide(
            deal_code=DealCode(found.deal_code),
            deal_name=found.deal_name,
            customer=found.customer,
            vendor=vendor,
            product=found.product,
            partner=found.partner,
            owner_user_id=UserId(found.owner_user_id),
            is_won=found.forecast_key == "won",
        ),
        attachment_count=int(found.attachment_count),
    )
