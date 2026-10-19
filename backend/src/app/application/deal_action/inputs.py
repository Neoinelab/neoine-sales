"""Action 유스케이스 입력(원시 타입). 값의 검증은 도메인 `ActionContent.parse`가 한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.domain.deal_action.value_objects import ActionContent

if TYPE_CHECKING:
    from datetime import date

    from app.application.choice import CatalogChoice
    from app.domain.action_type.values import ActionTypeRef
    from app.domain.deal.sync import SyncResolution


@dataclass(frozen=True, slots=True)
class ActionContentInput:
    """Action 내용 입력(등록·수정 공통). 소속 Deal은 경로로, 수행자·일시는 서버가 정한다."""

    action_type: CatalogChoice
    action: str
    next_action: str
    due_date: date | None
    memo: str = ""

    def to_content(self, action_type: ActionTypeRef) -> ActionContent:
        return ActionContent.parse(
            action_type=action_type,
            action=self.action,
            next_action=self.next_action,
            due_date=self.due_date,
            memo=self.memo,
        )


@dataclass(frozen=True, slots=True)
class StatusChangeInput:
    """Action을 기록하면서 함께 바꿀 Status 또는 Forecast. 규칙은 `ApplyDealChange`와 같다."""

    field: Literal["status_key", "forecast_key"]
    value: str
    resolution: SyncResolution | None = None


@dataclass(frozen=True, slots=True)
class DealActionInput:
    """Action 등록 입력: 내용과 선택적인 Status/Forecast 동시 변경."""

    content: ActionContentInput
    status_change: StatusChangeInput | None = None
