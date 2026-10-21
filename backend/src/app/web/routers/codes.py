"""코드(Status·Forecast) 관리. 조회는 로그인 사용자, 사용 수 조회와 변경은 admin 전용."""

from typing import Any

from fastapi import APIRouter, Depends, Response, status

from app.domain.code.values import CodeId, CodeKind
from app.web.dependencies import Provider
from app.web.permissions import require_admin
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.code import (
    CodeCreateRequest,
    CodeOrderRequest,
    CodeRenameRequest,
    CodeSetResponse,
    CodeUsageResponse,
    usage_responses,
)
from app.web.schemas.ids import PathId

router = APIRouter(prefix="/api/v1/codes", tags=["codes"])
ADMIN = [Depends(require_admin)]
ADMIN_ERRORS: dict[int | str, dict[str, Any]] = {403: PROBLEM}


@router.get("", response_model=CodeSetResponse)
async def list_codes(provider: Provider) -> CodeSetResponse:
    return CodeSetResponse.from_set(await provider.list_code_set().execute())


@router.get(
    "/usage",
    response_model=list[CodeUsageResponse],
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, 422: PROBLEM},
)
async def list_codes_with_usage(kind: CodeKind, provider: Provider) -> list[CodeUsageResponse]:
    return usage_responses(await provider.list_codes_with_usage().execute(kind))


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CodeUsageResponse,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **WRITE_ERRORS},
)
async def create_code(
    body: CodeCreateRequest, response: Response, provider: Provider
) -> CodeUsageResponse:
    item = await provider.register_code().execute(
        kind=body.kind, name=body.name, probability_hint=body.probability_hint
    )
    response.headers["Location"] = f"{router.prefix}/{item.code.id}"
    return CodeUsageResponse.from_usage(item)


@router.put(
    "/order",
    response_model=list[CodeUsageResponse],
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **WRITE_ERRORS},
)
async def reorder_codes(body: CodeOrderRequest, provider: Provider) -> list[CodeUsageResponse]:
    items = await provider.reorder_codes().execute(body.kind, body.ids())
    return usage_responses(items)


@router.patch(
    "/{code_id}",
    response_model=CodeUsageResponse,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **WRITE_ERRORS},
)
async def rename_code(
    code_id: PathId, body: CodeRenameRequest, provider: Provider
) -> CodeUsageResponse:
    item = await provider.rename_code().execute(CodeId(code_id), body.name)
    return CodeUsageResponse.from_usage(item)


@router.delete(
    "/{code_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=ADMIN,
    responses={**ADMIN_ERRORS, **READ_ERRORS, 409: PROBLEM},
)
async def delete_code(code_id: PathId, provider: Provider) -> None:
    await provider.delete_code().execute(CodeId(code_id))
