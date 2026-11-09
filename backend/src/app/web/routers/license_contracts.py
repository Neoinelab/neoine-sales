"""라이선스 계약: 목록·조회·계약 칸 수정·발급·갱신·종료·삭제.

읽기는 모든 역할, 쓰기는 WRITE 권한이고 삭제의 admin 판정은 도메인이 한다
(admin이 아니면 계약 존재와 무관하게 403 먼저, admin만 없음 404).
계약은 Deal이 Won이 될 때 자동으로만 생기므로 생성 API는 없다. 정적 경로를 `/{contract_id}`보다
먼저 두어 충돌을 막는다.
"""

from typing import Annotated, Any

from fastapi import Query, Response, status

from app.application.deal.inputs import Actor
from app.domain.license_contract.values import LicenseContractId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.ids import PathId
from app.web.schemas.license_contract import (
    LicenseContractFieldsRequest,
    LicenseContractPage,
    LicenseContractResponse,
    LicenseContractSearchParams,
    LicenseIssueRequest,
    contract_user_ids,
)
from app.web.schemas.user_ref import resolve_refs
from app.web.security import CurrentUser

router = BusinessRouter(prefix="/api/v1/license-contracts", tags=["license-contracts"])
LIST_ERRORS: dict[int | str, dict[str, Any]] = {422: PROBLEM}
CHANGE_ERRORS: dict[int | str, dict[str, Any]] = {404: PROBLEM, 422: PROBLEM}


def _actor(user: CurrentUser) -> Actor:
    return Actor(user_id=user.user_id, role=user.role)


async def _response(provider: Provider, rows: list[Any]) -> list[LicenseContractResponse]:
    refs = await resolve_refs(provider, contract_user_ids(rows))
    return [LicenseContractResponse.from_row(row, refs) for row in rows]


@router.get("", response_model=LicenseContractPage, responses=LIST_ERRORS)
async def list_license_contracts(
    params: Annotated[LicenseContractSearchParams, Query()], provider: Provider
) -> LicenseContractPage:
    page = await provider.list_license_contracts().execute(params.to_query())
    return LicenseContractPage(
        items=await _response(provider, list(page.items)),
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{contract_id}", response_model=LicenseContractResponse, responses=READ_ERRORS)
async def get_license_contract(contract_id: PathId, provider: Provider) -> LicenseContractResponse:
    row = await provider.get_license_contract().execute(LicenseContractId(contract_id))
    return (await _response(provider, [row]))[0]


@router.put("/{contract_id}", response_model=LicenseContractResponse, responses=CHANGE_ERRORS)
async def update_license_contract(
    contract_id: PathId,
    body: LicenseContractFieldsRequest,
    user: CurrentUser,
    provider: Provider,
) -> LicenseContractResponse:
    row = await provider.update_license_contract().execute(
        LicenseContractId(contract_id), body.to_fields(), _actor(user)
    )
    return (await _response(provider, [row]))[0]


@router.post("/{contract_id}/issue", response_model=LicenseContractResponse, responses=WRITE_ERRORS)
async def issue_license(
    contract_id: PathId, body: LicenseIssueRequest, user: CurrentUser, provider: Provider
) -> LicenseContractResponse:
    row = await provider.issue_license().execute(
        LicenseContractId(contract_id), body.to_input(), _actor(user)
    )
    return (await _response(provider, [row]))[0]


@router.post(
    "/{contract_id}/renewal",
    status_code=status.HTTP_201_CREATED,
    response_model=LicenseContractResponse,
    responses=WRITE_ERRORS,
)
async def renew_license(
    contract_id: PathId,
    body: LicenseIssueRequest,
    response: Response,
    user: CurrentUser,
    provider: Provider,
) -> LicenseContractResponse:
    row = await provider.renew_license().execute(
        LicenseContractId(contract_id), body.to_input(), _actor(user)
    )
    response.headers["Location"] = f"{router.prefix}/{row.contract.id}"
    return (await _response(provider, [row]))[0]


@router.post("/{contract_id}/end", response_model=LicenseContractResponse, responses=WRITE_ERRORS)
async def end_license_contract(
    contract_id: PathId, user: CurrentUser, provider: Provider
) -> LicenseContractResponse:
    row = await provider.end_license_contract().execute(
        LicenseContractId(contract_id), _actor(user)
    )
    return (await _response(provider, [row]))[0]


@router.delete(
    "/{contract_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={**READ_ERRORS, 403: PROBLEM},
)
async def delete_license_contract(
    contract_id: PathId, user: CurrentUser, provider: Provider
) -> None:
    await provider.delete_license_contract().execute(LicenseContractId(contract_id), _actor(user))
