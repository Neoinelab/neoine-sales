from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import Field

from app.application.deal_action.inputs import DealActionInput
from app.application.ports.deal_action_repository import (
    KEYWORD_MAX,
    DealActionQuery,
    DealActionSort,
)
from app.application.ports.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.domain.deal.value_objects import DealId
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import ActionType
from app.domain.user.value_objects import UserId
from app.web.schemas.common import Page, RequestModel, ResponseModel
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


class DealActionRequest(RequestModel):
    action_type: ActionType
    action: str
    acted_at: datetime
    actor_user_id: UUID
    next_action: str
    due_date: date
    memo: str = ""

    def to_input(self) -> DealActionInput:
        return DealActionInput(**self.model_dump())


class DealActionResponse(ResponseModel):
    deal_id: str
    action_type: ActionType
    action: str
    next_action: str | None
    due_date: date | None
    memo: str
    acted_at: datetime
    actor: UserRef

    @classmethod
    def from_entity(
        cls, action: DealAction, refs: Mapping[UserId, DomainUserRef]
    ) -> DealActionResponse:
        details = action.details
        return cls(
            id=str(action.id),
            created_at=action.created_at,
            updated_at=action.updated_at,
            deal_id=str(details.deal_id),
            action_type=details.action_type,
            action=details.action,
            next_action=details.next_action,
            due_date=details.due_date,
            memo=details.memo,
            acted_at=details.acted_at,
            actor=ref_of(refs, details.actor_user_id),
        )


class DealActionSearchParams(RequestModel):
    """활동 검색 쿼리 파라미터. 기간은 acted_from 이상 acted_to 미만, 계획 일정은 양끝 포함이다."""

    action_type: ActionType | None = None
    actor_user_id: UserId | None = None
    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    acted_from: datetime | None = None
    acted_to: datetime | None = None
    due_from: date | None = None
    due_to: date | None = None
    sort: DealActionSort = DealActionSort.ACTED_AT_DESC
    offset: Annotated[int, Field(ge=0)] = 0
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT

    def to_query(self, deal_id: UUID | None) -> DealActionQuery:
        criteria = self.model_dump(exclude={"deal_id", "actor_user_id"})
        return DealActionQuery(
            deal_id=DealId(deal_id) if deal_id else None,
            actor_user_id=self.actor_user_id,
            **criteria,
        )


class GlobalDealActionSearchParams(DealActionSearchParams):
    """Deal 구분 없이 검색할 때는 deal_id로도 좁힐 수 있다."""

    deal_id: UUID | None = None

    def to_query(self, deal_id: UUID | None = None) -> DealActionQuery:
        return super().to_query(deal_id or self.deal_id)


DealActionPage = Page[DealActionResponse]


async def action_responses(
    provider: UseCaseProvider, actions: Sequence[DealAction]
) -> list[DealActionResponse]:
    """활동자 표시 이름을 한 번에 풀어 응답 목록을 만든다."""
    refs = await resolve_refs(provider, [a.details.actor_user_id for a in actions])
    return [DealActionResponse.from_entity(a, refs) for a in actions]


async def action_response(provider: UseCaseProvider, action: DealAction) -> DealActionResponse:
    (item,) = await action_responses(provider, [action])
    return item
