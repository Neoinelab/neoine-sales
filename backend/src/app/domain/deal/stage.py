"""딜 단계와 단계 변경 이력."""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, NewType
from uuid import UUID

from app.domain.common.validation import require_aware

if TYPE_CHECKING:
    from datetime import datetime

    from app.domain.deal.value_objects import DealId
    from app.domain.user.value_objects import UserId

DealStageChangeId = NewType("DealStageChangeId", UUID)

REASON_MAX = 500


class DealStage(StrEnum):
    """딜 진행 단계. 선언 순서가 표시 순서(파이프라인 정렬 기준)다."""

    PROSPECTING = "prospecting"
    INTRODUCTION = "introduction"
    POC_PREPARATION = "poc_preparation"
    POC_COMPLETED = "poc_completed"
    TECHNICAL_EVALUATION = "technical_evaluation"
    PRICE_NEGOTIATION = "price_negotiation"
    CONTRACT_COMPLETED = "contract_completed"
    LOST = "lost"


INITIAL_STAGE = DealStage.PROSPECTING


@dataclass(frozen=True, slots=True)
class StageChanger:
    """단계를 바꾼 사용자. users.id만 남기고 표시 이름은 읽을 때 users에서 만든다."""

    user_id: UserId


@dataclass(frozen=True, slots=True)
class DealStageChange:
    """불변 단계 변경 이력 한 건."""

    id: DealStageChangeId
    deal_id: DealId
    from_stage: DealStage
    to_stage: DealStage
    reason: str | None
    changed_by: StageChanger
    changed_at: datetime

    def __post_init__(self) -> None:
        require_aware(self.changed_at, "changed_at")
