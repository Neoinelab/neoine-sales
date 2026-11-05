from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from app.domain.attachment.values import FileName
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.license_contract.values import ContractAttachmentId, LicenseContractId


class LicenseContractAttachmentRepository(Protocol):
    async def add(self, attachment: ContractAttachment) -> None:
        """없는 계약은 LicenseContractNotFoundError, 같은 (계약, 이름)은
        AttachmentNameTakenError, 업로더가 없으면 InvalidReferenceError("사용자").

        실패해도 같은 트랜잭션을 계속 쓸 수 있어야 한다.
        """
        ...

    async def get(self, attachment_id: ContractAttachmentId) -> ContractAttachment:
        """deal_code는 계약에서 채운다. 없으면 ContractAttachmentNotFoundError."""
        ...

    async def find_by_name(
        self, contract_id: LicenseContractId, file_name: FileName
    ) -> ContractAttachment | None:
        """같은 계약의 같은 이름(대소문자 구분). 없으면 None."""
        ...

    async def list_by_contract(
        self, contract_id: LicenseContractId
    ) -> Sequence[ContractAttachment]:
        """업로드 시각 내림차순, 같으면 id 내림차순."""
        ...

    async def update(self, attachment: ContractAttachment) -> None:
        """description·size·mime·storage_key·uploaded_by·uploaded_at·updated_at만 저장한다."""
        ...

    async def delete(self, attachment_id: ContractAttachmentId) -> None:
        """없으면 ContractAttachmentNotFoundError."""
        ...
