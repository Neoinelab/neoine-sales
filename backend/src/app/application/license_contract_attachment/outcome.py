from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.attachment.inputs import UploadOutcomeKind
    from app.domain.license_contract.attachment import ContractAttachment


@dataclass(frozen=True, slots=True)
class ContractUploadOutcome:
    """계약 첨부 업로드 결과. 종류는 Deal 첨부와 같고 건너뛰면 attachment가 없다."""

    kind: UploadOutcomeKind
    attachment: ContractAttachment | None
