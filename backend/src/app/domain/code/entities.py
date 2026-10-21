from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from app.domain.code.errors import CodeInUseError, CodeLockedError
from app.domain.code.values import (
    LOCKED_KEYS,
    PROBABILITY_HINT_MAX,
    CodeId,
    CodeKey,
    CodeKind,
    ForecastOutcome,
)
from app.domain.common.entity import AuditedEntity
from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(eq=False, kw_only=True)
class Code(AuditedEntity[CodeId]):
    """Status 또는 Forecast 코드 한 줄. 이름·순서는 바꿀 수 있고 key는 바뀌지 않는다."""

    kind: CodeKind
    key: CodeKey
    name: str
    order: int
    outcome: ForecastOutcome = ForecastOutcome.OPEN
    probability_hint: str | None = None

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.kind is CodeKind.STATUS:
            if self.probability_hint is not None:
                raise InvalidValueError("Status에는 확률 힌트를 둘 수 없습니다.")
            if self.outcome is not ForecastOutcome.OPEN:
                raise InvalidValueError("Status의 결과는 open만 가능합니다.")
        if self.probability_hint is not None and len(self.probability_hint) > PROBABILITY_HINT_MAX:
            raise InvalidValueError(f"확률 힌트는 {PROBABILITY_HINT_MAX}자 이내로 입력하세요.")

    @classmethod
    def create(  # noqa: PLR0913 - 코드 생성에 필요한 값이 모두 필수
        cls,
        *,
        entity_id: CodeId,
        kind: CodeKind,
        name: str,
        key: CodeKey,
        order: int,
        probability_hint: str | None,
        now: datetime,
    ) -> Self:
        """사용자가 만드는 일반 코드(outcome=open). 이름은 이미 정규화된 값이다.

        확률 힌트는 앞뒤 공백을 제거하고, 비면 None으로 둔다(길이는 제거 후 기준).
        """
        if probability_hint is not None:
            reject_nul(probability_hint, "확률 힌트")
            probability_hint = probability_hint.strip() or None
        return cls(
            id=entity_id,
            kind=kind,
            key=key,
            name=name,
            order=order,
            probability_hint=probability_hint,
            created_at=now,
            updated_at=now,
        )

    @property
    def locked(self) -> bool:
        return self.key.value in LOCKED_KEYS[self.kind]

    def rename(self, name: str, now: datetime) -> None:
        self.name = name
        self._touch(now)

    def place(self, order: int, now: datetime) -> None:
        self.order = order
        self._touch(now)

    def ensure_deletable(self, usage: int, action_usage: int = 0) -> None:
        """삭제할 수 없으면 거절한다: 잠금(먼저) -> 쓰는 Deal 수 -> 쓰는 Action 수 순이다."""
        if self.locked:
            raise CodeLockedError
        if usage > 0:
            raise CodeInUseError(usage)
        if action_usage > 0:
            raise CodeInUseError(action_usage, "Action")
