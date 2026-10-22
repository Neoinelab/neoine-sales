"""Status와 Forecast의 동기화 불변식: `contract_completed` ⇔ `won`.

프런트 `shared/model/sync.ts`의 `isSyncConsistent`와 같은 규칙이다. 상태·상수·불변식만 둔다.
단일 변경의 계획은 `sync_plan`, 확정은 `sync_finalize`에 있고 `sync`가 모두 다시 내보낸다.
"""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.deal.errors import SyncMismatchError

STATUS_PROSPECTING = "prospecting"
STATUS_CONTRACT_COMPLETED = "contract_completed"
FORECAST_PIPELINE = "pipeline"
FORECAST_WON = "won"
FORECAST_LOST = "lost"
# 종결 Forecast(Open Pipeline 아님). Risk 판정과 목록 기한초과·미업데이트 필터가 함께 쓴다.
CLOSED_FORECASTS: frozenset[str] = frozenset({FORECAST_WON, FORECAST_LOST})


class SyncField(StrEnum):
    STATUS = "status_key"
    FORECAST = "forecast_key"


@dataclass(frozen=True, slots=True)
class SyncState:
    """Deal의 Status key와 Forecast key."""

    status_key: str
    forecast_key: str


@dataclass(frozen=True, slots=True)
class CoChange:
    """단일 변경에 딸려 함께 바뀐 값(이력의 '함께 변경' 표기와 응답 notice에 쓴다)."""

    field: SyncField
    before: str
    after: str


def is_sync_consistent(state: SyncState) -> bool:
    return (state.status_key == STATUS_CONTRACT_COMPLETED) == (state.forecast_key == FORECAST_WON)


def ensure_sync_consistent(state: SyncState) -> None:
    if not is_sync_consistent(state):
        raise SyncMismatchError
