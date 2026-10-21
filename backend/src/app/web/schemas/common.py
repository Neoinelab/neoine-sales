from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequestModel(BaseModel):
    """요청 본문 기반 클래스. 모르는 필드는 오타일 가능성이 높아 거부한다."""

    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime


class Page[ItemT](BaseModel):
    items: list[ItemT]
    offset: int
    limit: int


class CountedPage[ItemT](Page[ItemT]):
    """전체 건수(total)를 함께 돌려주는 페이지."""

    total: int


class Problem(BaseModel):
    """RFC 9457 problem+json 본문(문서용)."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[dict[str, object]] | None = None
