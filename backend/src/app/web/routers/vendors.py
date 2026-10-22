"""Vendor 관리. 조회는 로그인 사용자, 생성·이름 변경·삭제는 admin 전용."""

from fastapi import Depends, Response, status

from app.domain.vendor.values import VendorId
from app.web.dependencies import Provider
from app.web.permissions import BusinessRouter, require_admin
from app.web.routers.responses import PROBLEM, READ_ERRORS, WRITE_ERRORS
from app.web.schemas.ids import PathId
from app.web.schemas.vendor import (
    VendorNameRequest,
    VendorResponse,
)

router = BusinessRouter(prefix="/api/v1/vendors", tags=["vendors"])
ADMIN = [Depends(require_admin)]
DELETE_ERRORS = {**READ_ERRORS, 409: PROBLEM}
CREATED = status.HTTP_201_CREATED
NO_CONTENT = status.HTTP_204_NO_CONTENT


@router.get("", response_model=list[VendorResponse])
async def list_vendors(provider: Provider) -> list[VendorResponse]:
    return [VendorResponse.from_usage(item) for item in await provider.list_vendors().execute()]


@router.post(
    "",
    status_code=CREATED,
    response_model=VendorResponse,
    dependencies=ADMIN,
    responses=WRITE_ERRORS,
)
async def create_vendor(
    body: VendorNameRequest, response: Response, provider: Provider
) -> VendorResponse:
    item = await provider.register_vendor().execute(body.name)
    response.headers["Location"] = f"{router.prefix}/{item.vendor.id}"
    return VendorResponse.from_usage(item)


@router.patch(
    "/{vendor_id}", response_model=VendorResponse, dependencies=ADMIN, responses=WRITE_ERRORS
)
async def rename_vendor(
    vendor_id: PathId, body: VendorNameRequest, provider: Provider
) -> VendorResponse:
    item = await provider.rename_vendor().execute(VendorId(vendor_id), body.name)
    return VendorResponse.from_usage(item)


@router.delete("/{vendor_id}", status_code=NO_CONTENT, dependencies=ADMIN, responses=DELETE_ERRORS)
async def delete_vendor(vendor_id: PathId, provider: Provider) -> None:
    await provider.delete_vendor().execute(VendorId(vendor_id))
