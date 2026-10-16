"""첨부 한 건: 조회, 다운로드, 삭제."""

from typing import Any
from uuid import UUID

from fastapi import status
from fastapi.responses import StreamingResponse

from app.application.deal.inputs import Actor
from app.domain.attachment.values import AttachmentId
from app.web.content_disposition import attachment_disposition
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.attachment import AttachmentResponse, attachment_response
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/attachments", tags=["attachments"])
OCTET_STREAM = "application/octet-stream"
DOWNLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "파일 내용(항상 octet-stream, attachment)",
        "content": {OCTET_STREAM: {"schema": {"type": "string", "format": "binary"}}},
    },
    404: PROBLEM,
    503: PROBLEM,
}


@router.get("/{attachment_id}", response_model=AttachmentResponse, responses=READ_ERRORS)
async def get_attachment(attachment_id: UUID, provider: Provider) -> AttachmentResponse:
    attachment = await provider.get_attachment().execute(AttachmentId(attachment_id))
    return await attachment_response(provider, attachment)


@router.get(
    "/{attachment_id}/download",
    response_class=StreamingResponse,
    responses=DOWNLOAD_RESPONSES,
)
async def download_attachment(attachment_id: UUID, provider: Provider) -> StreamingResponse:
    attachment, opened = await provider.download_attachment().execute(AttachmentId(attachment_id))
    headers = {
        "Content-Length": str(opened.size),
        "Content-Disposition": attachment_disposition(attachment.file_name.value),
    }
    return StreamingResponse(opened.chunks, media_type=OCTET_STREAM, headers=headers)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS)
async def delete_attachment(attachment_id: UUID, user: CurrentUser, provider: Provider) -> None:
    await provider.delete_attachment().execute(
        AttachmentId(attachment_id), Actor(user_id=user.user_id, role=user.role)
    )
