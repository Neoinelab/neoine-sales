"""첨부 응답 스키마. 도메인 객체를 그대로 노출하지 않는다."""

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.attachment.inputs import UploadOutcome
    from app.domain.attachment.entities import Attachment
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class AttachmentResponse(BaseModel):
    id: int
    deal_code: str
    file_name: str
    description: str
    size: int
    mime: str
    uploaded_by: UserRef
    uploaded_at: ServerDateTime

    @classmethod
    def from_entity(
        cls, attachment: Attachment, refs: Mapping[UserId, DomainUserRef]
    ) -> AttachmentResponse:
        return cls(
            id=attachment.id,
            deal_code=attachment.deal_code.value,
            file_name=attachment.file_name.value,
            description=attachment.description,
            size=attachment.size,
            mime=attachment.mime,
            uploaded_by=ref_of(refs, attachment.uploaded_by),
            uploaded_at=attachment.uploaded_at,
        )


class AttachmentUploadResponse(BaseModel):
    """건너뛰었으면(`skipped`) attachment가 null이다."""

    outcome: Literal["uploaded", "replaced", "skipped"]
    attachment: AttachmentResponse | None


class AttachmentList(BaseModel):
    items: list[AttachmentResponse]


async def attachment_responses(
    provider: UseCaseProvider, attachments: Sequence[Attachment]
) -> list[AttachmentResponse]:
    """업로더 표시 이름을 한 번에 풀어 응답 목록을 만든다."""
    refs = await resolve_refs(provider, [a.uploaded_by for a in attachments])
    return [AttachmentResponse.from_entity(a, refs) for a in attachments]


async def attachment_response(
    provider: UseCaseProvider, attachment: Attachment
) -> AttachmentResponse:
    (item,) = await attachment_responses(provider, [attachment])
    return item


async def upload_response(
    provider: UseCaseProvider, outcome: UploadOutcome
) -> AttachmentUploadResponse:
    attachment = outcome.attachment
    return AttachmentUploadResponse(
        outcome=outcome.kind.value,
        attachment=await attachment_response(provider, attachment) if attachment else None,
    )
