"""동기화 계획의 확정: 사용자의 답을 같은 규칙으로 다시 검증하고 결과·notice를 만든다."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.domain.common.errors import InvalidValueError
from app.domain.common.korean import with_ro
from app.domain.deal.sync_plan import (
    AskForecast,
    AskStatus,
    CodeCatalog,
    Independent,
    NeedRevenue,
    SyncPatch,
    SyncPlan,
)
from app.domain.deal.sync_state import CoChange, SyncField, SyncState
from app.domain.deal.values import RevenueAmount

if TYPE_CHECKING:
    from datetime import date

REVENUE_REQUIRED_MESSAGE = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED_MESSAGE = "함께 바꿀 값을 선택하세요."


@dataclass(frozen=True, slots=True)
class SyncResolution:
    """사용자가 계획에 답한 값."""

    revenue_amount: int | None = None
    revenue_date: date | None = None
    status_key: str | None = None
    forecast_key: str | None = None


@dataclass(frozen=True, slots=True)
class SyncApplied:
    """확정된 결과: 새 상태, (닫는 경우) 매출금액·매출일, 함께 바뀐 값, 안내 문구."""

    state: SyncState
    revenue: tuple[RevenueAmount, date] | None
    co_changed: tuple[CoChange, ...]
    notice: str | None


def finalize_plan(
    current: SyncState,
    plan: SyncPlan,
    resolution: SyncResolution | None,
    catalog: CodeCatalog,
) -> SyncApplied:
    """사용자의 답을 같은 규칙으로 다시 검증하고 결과를 만든다. 틀리면 InvalidValueError."""
    answer = resolution or SyncResolution()
    match plan:
        case Independent(patch):
            return SyncApplied(_merge(current, patch), None, (), None)
        case NeedRevenue():
            return _finalize_closing(current, plan, answer, catalog)
        case AskStatus():
            return _finalize_status_choice(current, plan, answer, catalog)
        case AskForecast():
            return _finalize_forecast_choice(current, plan, answer, catalog)


def _merge(current: SyncState, patch: SyncPatch) -> SyncState:
    return SyncState(
        status_key=patch.status_key or current.status_key,
        forecast_key=patch.forecast_key or current.forecast_key,
    )


def _quoted(name: str) -> str:
    """'이름'으로 / '이름'로: 조사는 따옴표 밖에 붙는다."""
    return f"'{name}'{with_ro(name)[len(name) :]}"


def _revenue_of(answer: SyncResolution) -> tuple[RevenueAmount, date]:
    if answer.revenue_amount is None or answer.revenue_date is None:
        raise InvalidValueError(REVENUE_REQUIRED_MESSAGE)
    try:
        amount = RevenueAmount(answer.revenue_amount)
    except InvalidValueError:
        raise InvalidValueError(REVENUE_REQUIRED_MESSAGE) from None
    return amount, answer.revenue_date


def _finalize_closing(
    current: SyncState, plan: NeedRevenue, answer: SyncResolution, catalog: CodeCatalog
) -> SyncApplied:
    revenue = _revenue_of(answer)
    state = _merge(current, plan.patch)
    if plan.requested is SyncField.STATUS:
        co = CoChange(SyncField.FORECAST, current.forecast_key, state.forecast_key)
    else:
        co = CoChange(SyncField.STATUS, current.status_key, state.status_key)
    notice = (
        f"Status가 {_quoted(catalog.status_name(state.status_key))}, "
        f"Forecast가 {_quoted(catalog.forecast_name(state.forecast_key))} 함께 변경되었습니다."
    )
    return SyncApplied(state, revenue, (co,) if co.before != co.after else (), notice)


def _finalize_status_choice(
    current: SyncState, plan: AskStatus, answer: SyncResolution, catalog: CodeCatalog
) -> SyncApplied:
    chosen = answer.status_key
    if chosen is None or chosen not in plan.options:
        raise InvalidValueError(CHOICE_REQUIRED_MESSAGE)
    state = _merge(current, SyncPatch(status_key=chosen, forecast_key=plan.patch.forecast_key))
    if chosen == current.status_key:
        return SyncApplied(state, None, (), None)
    co = CoChange(SyncField.STATUS, current.status_key, chosen)
    notice = f"Status가 {_quoted(catalog.status_name(chosen))} 함께 변경되었습니다."
    return SyncApplied(state, None, (co,), notice)


def _finalize_forecast_choice(
    current: SyncState, plan: AskForecast, answer: SyncResolution, catalog: CodeCatalog
) -> SyncApplied:
    chosen = answer.forecast_key
    if chosen is None or chosen not in plan.options:
        raise InvalidValueError(CHOICE_REQUIRED_MESSAGE)
    state = _merge(current, SyncPatch(status_key=plan.patch.status_key, forecast_key=chosen))
    if chosen == current.forecast_key:
        return SyncApplied(state, None, (), None)
    co = CoChange(SyncField.FORECAST, current.forecast_key, chosen)
    notice = f"Forecast가 {_quoted(catalog.forecast_name(chosen))} 함께 변경되었습니다."
    return SyncApplied(state, None, (co,), notice)
