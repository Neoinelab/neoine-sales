"""Action 유형 요청·응답 스키마. 이름 규칙 검사는 도메인이 한다."""

from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.web.schemas.common import RequestModel
from app.web.schemas.server_datetime import ServerDateTime
from app.web.schemas.user_ref import UserRef, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.application.action_type.dto import ActionTypeUsage
    from app.domain.user.value_objects import UserId
    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class ActionTypeNameRequest(RequestModel):
    name: str


class ActionTypeResponse(BaseModel):
    id: int
    name: str
    is_default: bool
    created_by: UserRef | None
    created_at: ServerDateTime
    updated_at: ServerDateTime
    usage_count: int

    @classmethod
    def from_usage(
        cls, item: ActionTypeUsage, refs: Mapping[UserId, DomainUserRef]
    ) -> ActionTypeResponse:
        action_type = item.action_type
        creator = action_type.created_by_user_id
        return cls(
            id=action_type.id,
            name=action_type.name,
            is_default=action_type.is_default,
            created_by=UserRef.from_domain(refs[creator]) if creator is not None else None,
            created_at=action_type.created_at,
            updated_at=action_type.updated_at,
            usage_count=item.usage_count,
        )


async def action_type_responses(
    provider: UseCaseProvider, items: Sequence[ActionTypeUsage]
) -> list[ActionTypeResponse]:
    refs = await resolve_refs(provider, [i.action_type.created_by_user_id for i in items])
    return [ActionTypeResponse.from_usage(item, refs) for item in items]
