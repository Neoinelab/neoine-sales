"""Vendor 요청·응답 스키마. 이름 검사(공백·길이·NUL)는 도메인이 한다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.web.schemas.common import RequestModel
from app.web.schemas.server_datetime import ServerDateTime

if TYPE_CHECKING:
    from app.application.vendor.dto import VendorUsage


class VendorNameRequest(RequestModel):
    name: str


class VendorResponse(BaseModel):
    id: int
    name: str
    usage_count: int
    created_at: ServerDateTime
    updated_at: ServerDateTime

    @classmethod
    def from_usage(cls, item: VendorUsage) -> VendorResponse:
        vendor = item.vendor
        return cls(
            id=vendor.id,
            name=vendor.name,
            usage_count=item.usage_count,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at,
        )
