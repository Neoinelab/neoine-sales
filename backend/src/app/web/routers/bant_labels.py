"""BANT Label. 조회는 로그인 사용자, 생성은 sales·admin, 이름 변경·삭제는 admin 전용."""

from fastapi import Depends, Response, status

from app.domain.bant.values import BantLabelId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter, require_admin
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.bant_label import (
    BantLabelCreateRequest,
    BantLabelRenameRequest,
    BantLabelResponse,
    label_responses,
)
from app.web.schemas.ids import PathId
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/bant-labels", tags=["bant-labels"])
ADMIN = [Depends(require_admin)]


@router.get("", response_model=list[BantLabelResponse])
async def list_bant_labels(provider: Provider) -> list[BantLabelResponse]:
    return await label_responses(provider, await provider.list_bant_labels().execute())


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=BantLabelResponse,
    responses=WRITE_ERRORS,
)
async def create_bant_label(
    body: BantLabelCreateRequest, response: Response, user: CurrentUser, provider: Provider
) -> BantLabelResponse:
    item = await provider.register_bant_label().execute(body.category, body.name, user.user_id)
    response.headers["Location"] = f"{router.prefix}/{item.label.id}"
    (result,) = await label_responses(provider, [item])
    return result


@router.patch(
    "/{label_id}", response_model=BantLabelResponse, dependencies=ADMIN, responses=WRITE_ERRORS
)
async def rename_bant_label(
    label_id: PathId, body: BantLabelRenameRequest, provider: Provider
) -> BantLabelResponse:
    item = await provider.rename_bant_label().execute(BantLabelId(label_id), body.name)
    (result,) = await label_responses(provider, [item])
    return result


@router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=ADMIN,
    responses={**READ_ERRORS, 409: PROBLEM},
)
async def delete_bant_label(label_id: PathId, provider: Provider) -> None:
    await provider.delete_bant_label().execute(BantLabelId(label_id))
