"""Status·Forecast 동기화 규칙의 공개 진입점.

책임별 모듈을 다시 내보낸다: 불변식·상태는 `sync_state`, 계획은 `sync_plan`,
확정·notice는 `sync_finalize`. 외부에서는 `app.domain.deal.sync`로만 가져온다.
"""

from app.domain.deal.errors import SYNC_MISMATCH_MESSAGE
from app.domain.deal.sync_finalize import (
    CHOICE_REQUIRED_MESSAGE,
    REVENUE_REQUIRED_MESSAGE,
    SyncApplied,
    SyncResolution,
    finalize_plan,
)
from app.domain.deal.sync_plan import (
    CLOSING,
    AskForecast,
    AskStatus,
    CodeCatalog,
    CodeName,
    Independent,
    NeedRevenue,
    SyncChange,
    SyncPatch,
    SyncPlan,
    plan_change,
)
from app.domain.deal.sync_sequence import (
    MAX_SYNC_STEPS,
    SYNC_CONFLICT_MESSAGE,
    SYNC_DUPLICATE_MESSAGE,
    SyncStep,
    finalize_sequence,
)
from app.domain.deal.sync_state import (
    FORECAST_LOST,
    FORECAST_PIPELINE,
    FORECAST_WON,
    STATUS_CONTRACT_COMPLETED,
    STATUS_PROSPECTING,
    CoChange,
    SyncField,
    SyncState,
    ensure_sync_consistent,
    is_sync_consistent,
)

__all__ = [
    "CHOICE_REQUIRED_MESSAGE",
    "CLOSING",
    "FORECAST_LOST",
    "FORECAST_PIPELINE",
    "FORECAST_WON",
    "MAX_SYNC_STEPS",
    "REVENUE_REQUIRED_MESSAGE",
    "STATUS_CONTRACT_COMPLETED",
    "STATUS_PROSPECTING",
    "SYNC_CONFLICT_MESSAGE",
    "SYNC_DUPLICATE_MESSAGE",
    "SYNC_MISMATCH_MESSAGE",
    "AskForecast",
    "AskStatus",
    "CoChange",
    "CodeCatalog",
    "CodeName",
    "Independent",
    "NeedRevenue",
    "SyncApplied",
    "SyncChange",
    "SyncField",
    "SyncPatch",
    "SyncPlan",
    "SyncResolution",
    "SyncState",
    "SyncStep",
    "ensure_sync_consistent",
    "finalize_plan",
    "finalize_sequence",
    "is_sync_consistent",
    "plan_change",
]
