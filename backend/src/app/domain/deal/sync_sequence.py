"""순차 동기화: 한 번에 최대 두 변경을 앞에서부터 적용하며 각각 직전 상태 기준으로 판정한다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from app.domain.common.errors import InvalidValueError
from app.domain.deal.sync_finalize import SyncApplied, SyncResolution, finalize_plan
from app.domain.deal.sync_plan import CodeCatalog, SyncChange, plan_change
from app.domain.deal.sync_state import SyncField, SyncState

if TYPE_CHECKING:
    from collections.abc import Sequence

SYNC_CONFLICT_MESSAGE: Final = (
    "먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요."
)
SYNC_DUPLICATE_MESSAGE: Final = "Status와 Forecast는 한 번에 각각 한 번만 바꿀 수 있습니다."
MAX_SYNC_STEPS: Final = 2


@dataclass(frozen=True, slots=True)
class SyncStep:
    """순차 변경 하나: 바꿀 값과 그 변경에 대한 사용자의 답."""

    change: SyncChange
    resolution: SyncResolution | None = None


def _value_of(state: SyncState, field: SyncField) -> str:
    return state.status_key if field is SyncField.STATUS else state.forecast_key


def finalize_sequence(
    current: SyncState, steps: Sequence[SyncStep], catalog: CodeCatalog
) -> tuple[SyncApplied, ...]:
    """steps를 순서대로 확정한다. 반환 state는 그 step까지의 누적 상태이며 부수효과는 없다."""
    fields = [step.change.field for step in steps]
    if len(steps) > MAX_SYNC_STEPS or len(set(fields)) != len(fields):
        raise InvalidValueError(SYNC_DUPLICATE_MESSAGE)
    results: list[SyncApplied] = []
    state = current
    for step in steps:
        plan = plan_change(state, step.change, catalog)
        results.append(finalize_plan(state, plan, step.resolution, catalog))
        state = results[-1].state
    if len(results) == MAX_SYNC_STEPS:
        first = steps[0].change.field
        if _value_of(results[1].state, first) != _value_of(results[0].state, first):
            raise InvalidValueError(SYNC_CONFLICT_MESSAGE)
    return tuple(results)
