"""라이선스 계약 테스트용 생성 도우미. 기본은 유효한 더미 값이다.

팩토리는 유스케이스·권한을 거치지 않고 필드로 직접 만든다(규칙 자체를 검증하는 테스트가 팩토리에
기대지 않도록). 도메인 모듈은 사용 시점에 가져온다(구현 전에도 이 모듈을 쓰는 다른 테스트의
수집이 막히지 않게).

계약(구현 담당이 맞춘다): `LicenseContract`는 키워드 전용 dataclass이고 필드는
`id, deal_code, status, term, license_start, license_end, fields, renewed_from_id, ended_at,
created_by, updated_by, created_at, updated_at`다. `ContractAttachment`도 키워드 전용이며
`ContractAttachment.upload(contract_id=, deal_code=, candidate=, size=, mime=, storage_key=,
uploaded_by=, now=, entity_id=)`로 만든다.
"""

from datetime import date
from typing import TYPE_CHECKING
from uuid import uuid4

from tests.factories import NOW, make_deal_code
from tests.support.ids import new_id
from tests.support.user_ids import ACTOR_ID

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.deal.code import DealCode
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.entities import LicenseContract
    from app.domain.user.value_objects import UserId

ISSUED = ("issued_new", "issued_renewal")


def make_fields(tech_owner: str = "", inspection: str = "none", note: str = "") -> object:
    """검증을 마친 계약 칸(`ContractFields`)."""
    from app.domain.license_contract.values import ContractFields, InspectionCycle  # noqa: PLC0415

    return ContractFields(tech_owner=tech_owner, inspection=InspectionCycle(inspection), note=note)


def make_contract(  # noqa: PLR0913 - 계약 필드가 모두 독립적인 선택지
    *,
    deal_code: DealCode | None = None,
    status: str = "not_issued",
    start: date | None = None,
    amount: int = 1,
    unit: str = "year",
    tech_owner: str = "",
    inspection: str = "none",
    note: str = "",
    renewed_from: int | None = None,
    by: UserId = ACTOR_ID,
    entity_id: int | None = None,
    now: datetime = NOW,
) -> LicenseContract:
    """저장하지 않은 계약. 발급·종료 상태는 start(기본 2026-01-01)와 기간을 채워 만든다.

    status가 not_issued면 기간이 없다. ended는 ended_at = now이고 기간이 있다.
    """
    from app.domain.license_contract.entities import LicenseContract  # noqa: PLC0415
    from app.domain.license_contract.term import license_end  # noqa: PLC0415
    from app.domain.license_contract.values import (  # noqa: PLC0415
        ContractFields,
        ContractStatus,
        InspectionCycle,
        LicenseContractId,
        LicenseTerm,
        TermUnit,
    )

    contract_status = ContractStatus(status)
    has_term = contract_status is not ContractStatus.NOT_ISSUED
    first = start or date(2026, 1, 1)
    term = LicenseTerm(amount=amount, unit=TermUnit(unit)) if has_term else None
    return LicenseContract(
        id=LicenseContractId(new_id() if entity_id is None else entity_id),
        deal_code=deal_code or make_deal_code(),
        status=contract_status,
        term=term,
        license_start=first if has_term else None,
        license_end=license_end(first, amount, TermUnit(unit)) if has_term else None,
        fields=ContractFields(
            tech_owner=tech_owner, inspection=InspectionCycle(inspection), note=note
        ),
        renewed_from_id=None if renewed_from is None else LicenseContractId(renewed_from),
        ended_at=now if contract_status is ContractStatus.ENDED else None,
        created_by=by,
        updated_by=by,
        created_at=now,
        updated_at=now,
    )


def make_contract_attachment(  # noqa: PLR0913 - 첨부 필드가 모두 독립적인 선택지
    contract: LicenseContract,
    *,
    name: str = "a.pdf",
    description: str = "",
    size: int = 10,
    mime: str = "application/pdf",
    storage_key: str | None = None,
    uploaded_by: UserId = ACTOR_ID,
    entity_id: int | None = None,
    now: datetime = NOW,
) -> ContractAttachment:
    """저장하지 않은 계약 첨부(`ContractAttachment.upload`). 저장 키 기본은 uuid4 hex."""
    from app.domain.attachment.values import UploadCandidate  # noqa: PLC0415
    from app.domain.license_contract.attachment import ContractAttachment  # noqa: PLC0415
    from app.domain.license_contract.values import ContractAttachmentId  # noqa: PLC0415

    return ContractAttachment.upload(
        contract_id=contract.id,
        deal_code=contract.deal_code,
        candidate=UploadCandidate.check(file_name=name, description=description, size=size),
        size=size,
        mime=mime,
        storage_key=storage_key or uuid4().hex,
        uploaded_by=uploaded_by,
        now=now,
        entity_id=ContractAttachmentId(new_id() if entity_id is None else entity_id),
    )
