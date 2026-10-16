"""Deal 하위 첨부: 목록 조회와 업로드(multipart). 개별 조작은 attachment_items.py."""

from typing import Annotated, Any

from fastapi import File, Form, Response, UploadFile, status

from app.application.attachment.inputs import UploadAttachmentInput, UploadOutcomeKind
from app.application.deal.inputs import Actor
from app.domain.attachment.values import OnExists
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.attachment import (
    AttachmentList,
    AttachmentUploadResponse,
    attachment_responses,
    upload_response,
)
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1", tags=["attachments"])
UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    404: PROBLEM,
    409: PROBLEM,
    422: PROBLEM,
    503: PROBLEM,
}


@router.get("/deals/{code}/attachments", response_model=AttachmentList, responses=READ_ERRORS)
async def list_attachments(code: str, provider: Provider) -> AttachmentList:
    found = await provider.list_attachments().execute(code)
    return AttachmentList(items=await attachment_responses(provider, found))


@router.post(
    "/deals/{code}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=AttachmentUploadResponse,
    responses={200: {"model": AttachmentUploadResponse}, **UPLOAD_ERRORS},
)
async def upload_attachment(  # noqa: PLR0913, PLR0917 - 폼 필드 3개 + 공통 의존성
    code: str,
    response: Response,
    user: CurrentUser,
    provider: Provider,
    file: Annotated[UploadFile | None, File()] = None,
    description: Annotated[str, Form()] = "",
    on_exists: Annotated[OnExists, Form()] = OnExists.ASK,
) -> AttachmentUploadResponse:
    data = UploadAttachmentInput(
        file_name=file.filename if file else None,
        declared_size=file.size if file else None,
        mime=file.content_type if file else None,
        description=description,
        on_exists=on_exists,
        source=file,
    )
    outcome = await provider.upload_attachment().execute(
        code, data, Actor(user_id=user.user_id, role=user.role)
    )
    if outcome.kind is UploadOutcomeKind.UPLOADED and outcome.attachment is not None:
        response.headers["Location"] = f"{router.prefix}/attachments/{outcome.attachment.id}"
    else:
        response.status_code = status.HTTP_200_OK
    return await upload_response(provider, outcome)
