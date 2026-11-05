"""계약 첨부: 목록·업로드(multipart)는 `/license-contracts/{id}/attachments`, 다운로드·삭제는
`/license-contract-attachments/{id}`. Deal 첨부 라우터와 같은 방식이다."""

from typing import Annotated, Any

from fastapi import File, Form, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.application.attachment.inputs import UploadAttachmentInput, UploadOutcomeKind
from app.application.deal.inputs import Actor
from app.domain.attachment.values import OnExists
from app.domain.license_contract.values import ContractAttachmentId, LicenseContractId
from app.web.content_disposition import attachment_disposition
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS
from app.web.schemas.ids import PathId
from app.web.schemas.license_contract_attachment import (
    ContractAttachmentList,
    ContractAttachmentUploadResponse,
    contract_attachment_responses,
    contract_upload_response,
)
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1", tags=["license-contracts"])
items_router = BusinessRouter(
    prefix="/api/v1/license-contract-attachments", tags=["license-contract-attachments"]
)
OCTET_STREAM = "application/octet-stream"
UPLOAD_ERRORS: dict[int | str, dict[str, Any]] = {
    404: PROBLEM,
    409: PROBLEM,
    422: PROBLEM,
    503: PROBLEM,
}
DOWNLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "파일 내용(항상 octet-stream, attachment)",
        "content": {OCTET_STREAM: {"schema": {"type": "string", "format": "binary"}}},
    },
    404: PROBLEM,
    503: PROBLEM,
}


@router.get(
    "/license-contracts/{contract_id}/attachments",
    response_model=ContractAttachmentList,
    responses=READ_ERRORS,
)
async def list_contract_attachments(
    contract_id: PathId, provider: Provider
) -> ContractAttachmentList:
    found = await provider.list_contract_attachments().execute(LicenseContractId(contract_id))
    return ContractAttachmentList(items=await contract_attachment_responses(provider, found))


@router.post(
    "/license-contracts/{contract_id}/attachments",
    status_code=status.HTTP_201_CREATED,
    response_model=ContractAttachmentUploadResponse,
    responses={200: {"model": ContractAttachmentUploadResponse}, **UPLOAD_ERRORS},
)
async def upload_contract_attachment(  # noqa: PLR0913, PLR0917 - 폼 필드 3개 + 공통 의존성
    contract_id: PathId,
    response: Response,
    user: CurrentUser,
    provider: Provider,
    file: Annotated[UploadFile | None, File()] = None,
    description: Annotated[str, Form()] = "",
    on_exists: Annotated[OnExists, Form()] = OnExists.ASK,
) -> ContractAttachmentUploadResponse:
    data = UploadAttachmentInput(
        file_name=file.filename if file else None,
        declared_size=file.size if file else None,
        mime=file.content_type if file else None,
        description=description,
        on_exists=on_exists,
        source=file,
    )
    outcome = await provider.upload_contract_attachment().execute(
        LicenseContractId(contract_id), data, Actor(user_id=user.user_id, role=user.role)
    )
    if outcome.kind is UploadOutcomeKind.UPLOADED and outcome.attachment is not None:
        response.headers["Location"] = f"{items_router.prefix}/{outcome.attachment.id}/download"
    else:
        response.status_code = status.HTTP_200_OK
    return await contract_upload_response(provider, outcome)


@items_router.get(
    "/{attachment_id}/download", response_class=StreamingResponse, responses=DOWNLOAD_RESPONSES
)
async def download_contract_attachment(
    attachment_id: PathId, provider: Provider
) -> StreamingResponse:
    attachment, opened = await provider.download_contract_attachment().execute(
        ContractAttachmentId(attachment_id)
    )
    headers = {
        "Content-Length": str(opened.size),
        "Content-Disposition": attachment_disposition(attachment.file_name.value),
    }
    return StreamingResponse(opened.chunks, media_type=OCTET_STREAM, headers=headers)


@items_router.delete(
    "/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=READ_ERRORS
)
async def delete_contract_attachment(
    attachment_id: PathId, user: CurrentUser, provider: Provider
) -> None:
    await provider.delete_contract_attachment().execute(
        ContractAttachmentId(attachment_id), Actor(user_id=user.user_id, role=user.role)
    )
