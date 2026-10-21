"""Vendor·Solution 요청·응답 스키마. 이름 검사(공백·길이·NUL)는 도메인이 한다."""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.web.schemas.common import RequestModel

if TYPE_CHECKING:
    from app.application.vendor.dto import SolutionUsage, VendorUsage


class VendorNameRequest(RequestModel):
    name: str


class SolutionNameRequest(RequestModel):
    name: str


class SolutionResponse(BaseModel):
    id: int
    vendor_id: int
    name: str
    usage_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_usage(cls, item: SolutionUsage) -> SolutionResponse:
        solution = item.solution
        return cls(
            id=solution.id,
            vendor_id=item.vendor_id,
            name=solution.name,
            usage_count=item.usage_count,
            created_at=solution.created_at,
            updated_at=solution.updated_at,
        )


class VendorResponse(BaseModel):
    id: int
    name: str
    usage_count: int
    created_at: datetime
    updated_at: datetime
    solutions: list[SolutionResponse]

    @classmethod
    def from_usage(cls, item: VendorUsage) -> VendorResponse:
        vendor = item.vendor
        return cls(
            id=vendor.id,
            name=vendor.name,
            usage_count=item.usage_count,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at,
            solutions=[SolutionResponse.from_usage(s) for s in item.solutions],
        )
