"""계약 첨부 응답 스키마. Deal 첨부와 같은 모양에 contract_id가 더해진다."""

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.license_contract_attachment.outcome import ContractUploadOutcome
    from app.domain.license_contract.attachment import ContractAttachment
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class ContractAttachmentResponse(BaseModel):
    id: int
    contract_id: int
    deal_code: str
    file_name: str
    description: str
    size: int
    mime: str
    uploaded_by: UserRef
    uploaded_at: ServerDateTime

    @classmethod
    def from_entity(
        cls, attachment: ContractAttachment, refs: Mapping[UserId, DomainUserRef]
    ) -> ContractAttachmentResponse:
        return cls(
            id=attachment.id,
            contract_id=attachment.contract_id,
            deal_code=attachment.deal_code.value,
            file_name=attachment.file_name.value,
            description=attachment.description,
            size=attachment.size,
            mime=attachment.mime,
            uploaded_by=ref_of(refs, attachment.uploaded_by),
            uploaded_at=attachment.uploaded_at,
        )


class ContractAttachmentUploadResponse(BaseModel):
    """건너뛰었으면(`skipped`) attachment가 null이다."""

    outcome: Literal["uploaded", "replaced", "skipped"]
    attachment: ContractAttachmentResponse | None


class ContractAttachmentList(BaseModel):
    items: list[ContractAttachmentResponse]


async def contract_attachment_responses(
    provider: UseCaseProvider, attachments: Sequence[ContractAttachment]
) -> list[ContractAttachmentResponse]:
    """업로더 표시 이름을 한 번에 풀어 응답 목록을 만든다."""
    refs = await resolve_refs(provider, [a.uploaded_by for a in attachments])
    return [ContractAttachmentResponse.from_entity(a, refs) for a in attachments]


async def contract_attachment_response(
    provider: UseCaseProvider, attachment: ContractAttachment
) -> ContractAttachmentResponse:
    (item,) = await contract_attachment_responses(provider, [attachment])
    return item


async def contract_upload_response(
    provider: UseCaseProvider, outcome: ContractUploadOutcome
) -> ContractAttachmentUploadResponse:
    attachment = outcome.attachment
    return ContractAttachmentUploadResponse(
        outcome=outcome.kind.value,
        attachment=await contract_attachment_response(provider, attachment) if attachment else None,
    )
