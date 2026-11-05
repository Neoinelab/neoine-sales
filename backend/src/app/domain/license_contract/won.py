"""Won 전이 판정. Won은 Forecast `won`이며 불변식상 Status `contract_completed`와 같다."""

from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.deal.sync import FORECAST_WON
from app.domain.license_contract.errors import LicenseRequiresWonError, WonExitBlockedError

if TYPE_CHECKING:
    from app.domain.deal.sync import SyncState
    from app.domain.license_contract.entities import LicenseContract


class WonTransition(StrEnum):
    ENTERED = "entered"
    LEFT = "left"
    NONE = "none"


def is_won(state: SyncState) -> bool:
    """Forecast가 won이면 Won이다(불변식상 Status contract_completed와 같다)."""
    return state.forecast_key == FORECAST_WON


def won_transition(before: SyncState | None, after: SyncState) -> WonTransition:
    """before가 None이면 신규 등록이다."""
    was_won = before is not None and is_won(before)
    now_won = is_won(after)
    if now_won and not was_won:
        return WonTransition.ENTERED
    if was_won and not now_won:
        return WonTransition.LEFT
    return WonTransition.NONE


def ensure_can_leave_won(issued: LicenseContract | None) -> None:
    """발급 상태 계약이 있으면 Won을 벗어날 수 없다. None(발급 계약 없음)이면 통과."""
    if issued is not None:
        raise WonExitBlockedError


def ensure_issuable_on(state: SyncState) -> None:
    """Deal이 Won이 아니면 발급·갱신할 수 없다."""
    if not is_won(state):
        raise LicenseRequiresWonError
