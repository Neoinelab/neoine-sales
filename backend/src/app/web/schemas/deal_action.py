import re
from datetime import date
from typing import TYPE_CHECKING, Annotated, Self

from pydantic import BaseModel, BeforeValidator, Field, StrictBool, model_validator

from app.application.deal_action.inputs import (
    ActionContentInput,
    DealActionInput,
    DealActionUpdateInput,
    NextActionStatusInput,
    StatusChangeInput,
)
from app.application.ports.deal_action_repository import (
    KEYWORD_MAX,
    DealActionQuery,
    DealActionSort,
    NextActionStatusFilter,
)
from app.domain.deal.code import DealCode
from app.domain.deal.errors import DealNotFoundError
from app.domain.deal.sync import SyncResolution
from app.domain.deal_action.entities import DealAction
from app.domain.deal_action.next_action_status import NextActionStatus
from app.domain.deal_action.value_objects import DealActionId
from app.domain.user.value_objects import UserId
from app.web.schemas.choice import CatalogChoiceRequest
from app.web.schemas.common import RequestModel, ResponseModel
from app.web.schemas.deal_change import CodeChange, ResolutionRequest
from app.web.schemas.deal_response import NamedRefResponse
from app.web.schemas.ids import BodyId, QueryId
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
    """Action 내용. 수행 일시·수행자·스냅숏은 서버가 정하므로 받지 않는다. 길이 제한은 없다.

    필수는 action_type뿐이다. 진행사항과 Next Action 중 하나는 있어야 하고(둘 다 비면 422),
    Due Date는 Next Action이 있을 때만 필수다.
    """

    action_type: CatalogChoiceRequest
    action: str = ""
    next_action: str = ""
    due_date: date | None = None  # 입력 조합 규칙(진행사항·Next Action·Due)은 도메인이 판정한다

    def to_content(self) -> ActionContentInput:
        return ActionContentInput(
            action_type=self.action_type.to_choice(),
            action=self.action,
            next_action=self.next_action,
            due_date=self.due_date,
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


_PLAIN_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _plain_date(value: object) -> object:
    # lax date는 자정 시각이 붙은 문자열·숫자도 받으므로 YYYY-MM-DD 문자열만 통과시킨다.
    if value is None or (isinstance(value, str) and _PLAIN_DATE.fullmatch(value)):
        return value
    raise ValueError("acted_on은 YYYY-MM-DD 형식의 날짜여야 합니다.")


class DealActionCreateRequest(ActionContentRequest):
    """`status_change`(단건)와 `status_changes`(최대 2건, 필드 중복 불가)는 함께 쓸 수 없다."""

    status_change: Annotated[
        ActionStatusChangeRequest | None,
        Field(
            description=(
                "단건 변경(하위 호환). status_changes와 함께 보내면"
                "(빈 배열 포함, null은 변경 없음) 422로 거부된다. "
                "여러 건은 순서가 보장되는 status_changes를 쓴다."
            )
        ),
    ] = None
    status_changes: Annotated[
        list[ActionStatusChangeRequest] | None,
        Field(
            max_length=2,
            description=(
                "최대 2건(field 중복 불가). 배열 순서대로 적용하며, 두 번째 변경은 첫 변경을 "
                "적용한 뒤의 상태로 동기화 규칙을 판정한다. 먼저 바꾼 값과 충돌하면 "
                "422 invalid-value. status_change와 함께 보내면(빈 배열 포함, null은 제외) 422."
            ),
        ),
    ] = None
    close_previous_next_action_id: Annotated[
        BodyId | None,
        Field(
            description=(
                "저장하며 종료(수행)로 바꿀 이전 Next Action의 Action id. 그 Deal의 "
                "'Next Action이 있는 가장 최근 Action'과 다르면 409(invalid-state), "
                "담당자 본인·admin이 아니면 403. 이미 종료된 행이면 상태를 바꾸지 않는다. "
                "생략하거나 null이면 이전 행을 바꾸지 않는다."
            )
        ),
    ] = None
    acted_on: Annotated[
        date | None,
        BeforeValidator(_plain_date),
        Field(
            description=(
                "수행일(YYYY-MM-DD, 선택). 생략하거나 null이면 오늘(서버 업무 날짜)로 기록한다."
            )
        ),
    ] = None
    comment: Annotated[
        str,
        Field(
            description=(
                "새 Action에 함께 남길 Action Comment(선택). 생략하거나 비었거나 공백뿐이면 "
                "Comment를 만들지 않는다. NUL 문자는 422."
            )
        ),
    ] = ""
    delete_license_contracts: Annotated[
        StrictBool,
        Field(
            description=(
                "status_changes가 Won을 벗어나게 할 때 그 Deal의 라이선스 계약도 삭제한다"
                "(아니면 무시)."
            )
        ),
    ] = False

    @model_validator(mode="after")
    def _check_status_changes(self) -> Self:
        # null은 '변경 없음'으로 본다. 빈 배열은 값이 있는 것으로 보아
        # status_change와 함께 오면 거부한다.
        if self.status_change is not None and self.status_changes is not None:
            raise ValueError("status_change와 status_changes는 함께 보낼 수 없습니다.")
        fields = [c.change.field for c in self.status_changes or []]
        if len(set(fields)) != len(fields):
            raise ValueError("status_changes에 같은 field가 두 번 있습니다.")
        return self

    def to_input(self) -> DealActionInput:
        requests = self.status_changes or ([self.status_change] if self.status_change else [])
        changes = tuple(r.to_input() for r in requests)
        previous = self.close_previous_next_action_id
        return DealActionInput(
            content=self.to_content(),
            acted_on=self.acted_on,
            status_changes=changes,
            close_previous_next_action_id=None if previous is None else DealActionId(previous),
            delete_license_contracts=self.delete_license_contracts,
            comment=self.comment,
        )


class DealActionUpdateRequest(ActionContentRequest):
    acted_on: Annotated[
        date | None,
        BeforeValidator(_plain_date),
        Field(
            description=(
                "수정할 수행일(YYYY-MM-DD, 선택). 생략하거나 null이면 기존 수행일을 유지한다."
            )
        ),
    ] = None

    def to_input(self) -> DealActionUpdateInput:
        return DealActionUpdateInput(content=self.to_content(), acted_on=self.acted_on)


class NextActionStatusRequest(RequestModel):
    """Next Action 상태 변경. comment는 종료할 때 그 Action에 남길 Comment(open과는 함께 불가)."""

    status: NextActionStatus
    comment: str = ""

    def to_input(self) -> NextActionStatusInput:
        return NextActionStatusInput(status=self.status, comment=self.comment)


class DealActionResponse(ResponseModel):
    deal_code: str
    action_type: NamedRefResponse
    action: str | None
    next_action: str | None
    due_date: date | None
    next_action_status: NextActionStatus | None
    next_action_closed_on: date | None
    acted_on: date
    actor: UserRef
    status_key: str
    forecast_key: str

    @classmethod
    def from_entity(
        cls, action: DealAction, refs: Mapping[UserId, DomainUserRef]
    ) -> DealActionResponse:
        content = action.content
        state = action.next_action_state
        return cls(
            id=str(action.id),
            created_at=action.created_at,
            updated_at=action.updated_at,
            deal_code=action.deal_code.value,
            action_type=NamedRefResponse(
                id=str(content.action_type.id), name=content.action_type.name
            ),
            action=content.action,
            next_action=content.next_action,
            due_date=content.due_date,
            next_action_status=state.status if state else None,
            next_action_closed_on=state.closed_on if state else None,
            acted_on=action.acted_on,
            actor=ref_of(refs, action.actor_user_id),
            status_key=action.snapshot.status_key,
            forecast_key=action.snapshot.forecast_key,
        )


class DealActionList(BaseModel):
    """Deal 하나의 Action 전부. 페이지는 없다."""

    items: list[DealActionResponse]


class DealActionSearchParams(RequestModel):
    """Action 검색 쿼리. 수행일(acted_*)·Due Date(due_*)는 날짜이고 양끝을 포함한다."""

    action_type_id: QueryId | None = None
    actor_user_id: QueryId | None = None
    keyword: Annotated[str | None, Field(max_length=KEYWORD_MAX)] = None
    acted_from: date | None = None
    acted_to: date | None = None
    due_from: date | None = None
    due_to: date | None = None
    next_action_status: NextActionStatusFilter | None = None
    sort: DealActionSort = DealActionSort.ACTED_AT_DESC

    def to_query(self, code: str) -> DealActionQuery:
        criteria = self.model_dump(exclude={"actor_user_id"})
        return DealActionQuery(
            deal_code=parse_deal_code(code),
            actor_user_id=None if self.actor_user_id is None else UserId(self.actor_user_id),
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
