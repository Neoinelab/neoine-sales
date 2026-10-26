"""BANT Label 요청·응답 스키마. 빈 이름 검사는 도메인이 한다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.domain.bant.values import BantCategory
from app.web.schemas.common import RequestModel
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.bant.dto import LabelUsage
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class BantLabelCreateRequest(RequestModel):
    category: BantCategory
    name: str


class BantLabelRenameRequest(RequestModel):
    name: str


class BantLabelResponse(BaseModel):
    id: int
    category: BantCategory
    name: str
    is_default: bool
    created_by: UserRef | None
    created_at: ServerDateTime
    updated_at: ServerDateTime
    usage_count: int

    @classmethod
    def from_usage(
        cls, item: LabelUsage, refs: Mapping[UserId, DomainUserRef]
    ) -> BantLabelResponse:
        label = item.label
        creator = label.created_by_user_id
        return cls(
            id=label.id,
            category=label.category,
            name=label.name,
            is_default=label.is_default,
            created_by=UserRef.from_domain(refs[creator]) if creator is not None else None,
            created_at=label.created_at,
            updated_at=label.updated_at,
            usage_count=item.usage_count,
        )


async def label_responses(
    provider: UseCaseProvider, items: Sequence[LabelUsage]
) -> list[BantLabelResponse]:
    refs = await resolve_refs(provider, [i.label.created_by_user_id for i in items])
    return [BantLabelResponse.from_usage(item, refs) for item in items]
