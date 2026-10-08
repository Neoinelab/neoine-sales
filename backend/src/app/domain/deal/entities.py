from dataclasses import dataclass
from typing import TYPE_CHECKING, Self
from uuid import uuid4

from app.domain.auth.principal import SUBJECT_MAX
from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import InvalidStateError
from app.domain.common.validation import optional_text, required_text
from app.domain.deal.stage import (
    INITIAL_STAGE,
    REASON_MAX,
    DealStage,
    DealStageChange,
    DealStageChangeId,
    StageChanger,
)
from app.domain.deal.value_objects import DealDetails, DealId

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Deal(AuditedEntity[DealId]):
    details: DealDetails
    stage: DealStage = INITIAL_STAGE
    owner_user_id: str | None = None  # 등록한 로그인 사용자의 subject. 등록 후 바꾸지 않는다

    def __post_init__(self) -> None:
        super().__post_init__()
        self.owner_user_id = optional_text(
            self.owner_user_id, "등록 사용자", max_length=SUBJECT_MAX
        )

    @classmethod
    def create(
        cls,
        details: DealDetails,
        now: datetime,
        *,
        entity_id: DealId | None = None,
        owner_user_id: str | None = None,
    ) -> Self:
        return cls(
            id=entity_id or DealId(uuid4()),
            details=details,
            created_at=now,
            updated_at=now,
            owner_user_id=owner_user_id,
        )

    def update(self, details: DealDetails, now: datetime) -> None:
        self._ensure_active()
        self._touch(now)
        self.details = details

    def change_stage(
        self, to: DealStage, *, reason: str | None, changed_by: StageChanger, now: datetime
    ) -> DealStageChange:
        """단계를 바꾸고 이력 한 건을 돌려준다(저장은 유스케이스가 한다).

        검증 순서: 삭제 여부, 같은 단계, 사유(실주는 필수, 그 외는 선택 메모).
        """
        self._ensure_active()
        if to is self.stage:
            raise InvalidStateError("이미 같은 단계입니다")
        if to is DealStage.LOST:
            note: str | None = required_text(reason or "", "실주 사유", max_length=REASON_MAX)
        else:
            note = optional_text(reason, "단계 변경 사유", max_length=REASON_MAX)
        change = DealStageChange(
            id=DealStageChangeId(uuid4()),
            deal_id=self.id,
            from_stage=self.stage,
            to_stage=to,
            reason=note,
            changed_by=changed_by,
            changed_at=now,
        )
        self._touch(now)
        self.stage = to
        return change
