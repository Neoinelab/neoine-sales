from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.attachment.errors import (
    AttachmentDeleteForbiddenError,
    AttachmentReplaceForbiddenError,
)
from app.domain.attachment.policy import can_delete_attachment
from app.domain.common.entity import AuditedEntity
from app.domain.common.validation import require_aware
from app.domain.license_contract.values import ContractAttachmentId

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.attachment.values import FileName, UploadCandidate
    from app.domain.auth.principal import Role
    from app.domain.deal.code import DealCode
    from app.domain.license_contract.values import LicenseContractId
    from app.domain.user.value_objects import UserId, UserRef


@dataclass(eq=False, kw_only=True)
class ContractAttachment(AuditedEntity[ContractAttachmentId]):
    """계약에 올린 파일 한 건. 규칙은 Deal 첨부와 같다.

    deal_code는 응답 표시용이며 저장 위치는 계약 id로 정한다. DB에는 저장하지 않고
    조회할 때 계약에서 채운다.
    """

    contract_id: LicenseContractId
    deal_code: DealCode
    file_name: FileName
    description: str
    size: int
    mime: str
    storage_key: str  # 디스크 파일 이름. 교체할 때마다 새 키
    uploaded_by: UserId
    uploaded_at: datetime

    @classmethod
    def upload(  # noqa: PLR0913 - 업로드 시점에 정해지는 값이 모두 독립적인 필수 입력
        cls,
        *,
        contract_id: LicenseContractId,
        deal_code: DealCode,
        candidate: UploadCandidate,
        size: int,
        mime: str,
        storage_key: str,
        uploaded_by: UserId,
        now: datetime,
        entity_id: ContractAttachmentId,
    ) -> Self:
        return cls(
            id=entity_id,
            contract_id=contract_id,
            deal_code=deal_code,
            file_name=candidate.file_name,
            description=candidate.description,
            size=size,
            mime=mime,
            storage_key=storage_key,
            uploaded_by=uploaded_by,
            uploaded_at=now,
            created_at=now,
            updated_at=now,
        )

    def __post_init__(self) -> None:
        super().__post_init__()
        require_aware(self.uploaded_at, "uploaded_at")

    def replace(  # noqa: PLR0913
        self,
        *,
        description: str,
        size: int,
        mime: str,
        storage_key: str,
        uploaded_by: UserId,
        now: datetime,
    ) -> str:
        """내용을 새 파일로 바꾸고 이전 저장 키를 돌려준다(이전 디스크 파일은 호출자가 지운다)."""
        require_aware(now, "now")
        previous = self.storage_key
        self.description = description
        self.size = size
        self.mime = mime
        self.storage_key = storage_key
        self.uploaded_by = uploaded_by
        self.uploaded_at = now
        self._touch(now)
        return previous

    def ensure_deletable_by(self, user_id: UserId, role: Role, uploader: UserRef) -> None:
        if not can_delete_attachment(user_id, role, uploader):
            raise AttachmentDeleteForbiddenError

    def ensure_replaceable_by(self, user_id: UserId, role: Role, uploader: UserRef) -> None:
        """교체 권한은 삭제 권한과 같다."""
        if not can_delete_attachment(user_id, role, uploader):
            raise AttachmentReplaceForbiddenError
