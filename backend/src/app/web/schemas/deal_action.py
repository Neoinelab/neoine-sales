from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field

from app.application.deal_action.inputs import (
    ActionContentInput,
    DealActionInput,
    StatusChangeInput,
)
from app.application.ports.deal_action_repository import (
    KEYWORD_MAX,
    DealActionQuery,
    DealActionSort,
)
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncResolution
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.value_objects import ActionType
from app.domain.user.value_objects import UserId
from app.web.schemas.common import RequestModel, ResponseModel
from app.web.schemas.deal_change import CodeChange, ResolutionRequest
from app.web.schemas.user_ref import UserRef, ref_of, resolve_refs

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.domain.user.value_objects import UserRef as DomainUserRef
    from app.web.use_case_provider import UseCaseProvider


def parse_deal_code(raw: str) -> DealCode:
    """경로의 Deal code. 형식이 틀린 값은 없는 Deal과 같은 404다."""
    code = DealCode.parse_or_none(raw)
    if code is None:
        raise DealNotFoundError(raw)
    return code


class ActionContentRequest(RequestModel):
    """Action 내용. 수행 일시·수행자·스냅숏은 서버가 정하므로 받지 않는다. 길이 제한은 없다."""

    action_type: ActionType
    action: str
    next_action: str
    due_date: date | None = None  # 누락·null은 도메인 문구("Due Date를 입력하세요.")로 거절한다
    memo: str = ""

    def to_content(self) -> ActionContentInput:
        return ActionContentInput(
            action_type=self.action_type,
            action=self.action,
            next_action=self.next_action,
            due_date=self.due_date,
            memo=self.memo,
        )


class ActionStatusChangeRequest(RequestModel):
    """Action을 기록하면서 함께 바꿀 Status 또는 Forecast."""

    change: CodeChange
    resolution: ResolutionRequest | None = None

    def to_input(self) -> StatusChangeInput:
        resolution = (
            SyncResolution(**self.resolution.model_dump()) if self.resolution is not None else None
        )
        return StatusChangeInput(
            field=self.change.field, value=self.change.value, resolution=resolution
        )


class DealActionCreateRequest(ActionContentRequest):
    status_change: ActionStatusChangeRequest | None = None

    def to_input(self) -> DealActionInput:
        change = self.status_change.to_input() if self.status_change is not None else None
        return DealActionInput(content=self.to_content(), status_change=change)


class DealActionUpdateRequest(ActionContentRequest):
    def to_input(self) -> ActionContentInput:
        return self.to_content()


class DealActionResponse(ResponseModel):
    deal_code: str
    action_type: ActionType
    action: str
    next_action: str
    due_date: date
    memo: str
    acted_at: datetime
    actor: UserRef
    status_key: str
    forecast_key: str

    @classmethod
    def from_entity(
        cls, action: DealAction, refs: Mapping[UserId, DomainUserRef]
    ) -> DealActionResponse:
        content = action.content
        return cls(
            id=str(action.id),
            created_at=action.created_at,
            updated_at=action.updated_at,
            deal_code=action.deal_code.value,
            action_type=content.action_type,
            action=content.action,
            next_action=content.next_action,
            due_date=content.due_date,
            memo=content.memo,
            acted_at=action.acted_at,
            actor=ref_of(refs, action.actor_user_id),
            status_key=action.snapshot.status_key,
            forecast_key=action.snapshot.forecast_key,
        )


class DealActionList(BaseModel):
    """Deal 하나의 Action 전부. 페이지는 없다."""

    items: list[DealActionResponse]


class DealActionSearchParams(RequestModel):
    """Action 검색 쿼리. 수행일(acted_*)·Due Date(due_*)는 날짜이고 양끝을 포함한다."""

    action_type: ActionType | None = None
    actor_user_id: UserId | None = None
    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    acted_from: date | None = None
    acted_to: date | None = None
    due_from: date | None = None
    due_to: date | None = None
    sort: DealActionSort = DealActionSort.ACTED_AT_DESC

    def to_query(self, code: str) -> DealActionQuery:
        criteria = self.model_dump(exclude={"actor_user_id"})
        return DealActionQuery(
            deal_code=parse_deal_code(code),
            actor_user_id=self.actor_user_id,
            **criteria,
        )


async def action_responses(
    provider: UseCaseProvider, actions: Sequence[DealAction]
) -> list[DealActionResponse]:
    """수행자 표시 이름을 한 번에 풀어 응답 목록을 만든다."""
    refs = await resolve_refs(provider, [a.actor_user_id for a in actions])
    return [DealActionResponse.from_entity(a, refs) for a in actions]


async def action_response(provider: UseCaseProvider, action: DealAction) -> DealActionResponse:
    (item,) = await action_responses(provider, [action])
    return item
