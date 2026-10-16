"""단일 변경의 동기화 계획: 코드 카탈로그, 계획 4종, `plan_change`(부수효과 없음)."""

from dataclasses import dataclass

from app.domain.deal.sync_state import (
    FORECAST_LOST,
    FORECAST_WON,
    STATUS_CONTRACT_COMPLETED,
    SyncField,
    SyncState,
)


@dataclass(frozen=True, slots=True)
class CodeName:
    key: str
    name: str


@dataclass(frozen=True, slots=True)
class CodeCatalog:
    """현재 Status·Forecast 코드(key와 이름, order 순). 규칙은 key, 이름은 notice에만 쓴다."""

    statuses: tuple[CodeName, ...]
    forecasts: tuple[CodeName, ...]

    def status_name(self, key: str) -> str:
        return next((c.name for c in self.statuses if c.key == key), key)

    def forecast_name(self, key: str) -> str:
        return next((c.name for c in self.forecasts if c.key == key), key)

    def status_keys_except(self, excluded: str) -> tuple[str, ...]:
        return tuple(c.key for c in self.statuses if c.key != excluded)

    def forecast_keys_except(self, excluded: str) -> tuple[str, ...]:
        return tuple(c.key for c in self.forecasts if c.key != excluded)


@dataclass(frozen=True, slots=True)
class SyncChange:
    """사용자가 바꾸려는 값 하나."""

    field: SyncField
    value: str


@dataclass(frozen=True, slots=True)
class SyncPatch:
    """계획이 확정하는 값. None이면 그대로 둔다."""

    status_key: str | None = None
    forecast_key: str | None = None


@dataclass(frozen=True, slots=True)
class Independent:
    """다른 값이 함께 바뀌지 않는 변경."""

    patch: SyncPatch


@dataclass(frozen=True, slots=True)
class NeedRevenue:
    """Won·계약완료로 닫는 변경: 매출금액과 매출일이 필요하다."""

    patch: SyncPatch
    requested: SyncField


@dataclass(frozen=True, slots=True)
class AskStatus:
    """Forecast가 Won/Lost에서 벗어나는 변경: 함께 바꿀 Status를 골라야 한다."""

    options: tuple[str, ...]
    default_key: str | None
    patch: SyncPatch


@dataclass(frozen=True, slots=True)
class AskForecast:
    """계약완료에서 벗어나는 변경: 함께 바꿀 Forecast를 골라야 한다."""

    options: tuple[str, ...]
    patch: SyncPatch


type SyncPlan = Independent | NeedRevenue | AskStatus | AskForecast

CLOSING = SyncPatch(status_key=STATUS_CONTRACT_COMPLETED, forecast_key=FORECAST_WON)


def plan_change(current: SyncState, change: SyncChange, catalog: CodeCatalog) -> SyncPlan:
    """단일 변경이 동기화 규칙에 따라 무엇을 더 요구하는지 정한다(부수효과 없음)."""
    if change.field is SyncField.STATUS:
        return _plan_status(current, change.value, catalog)
    return _plan_forecast(current, change.value, catalog)


def _plan_status(current: SyncState, value: str, catalog: CodeCatalog) -> SyncPlan:
    patch = SyncPatch(status_key=value)
    if value == current.status_key:
        return Independent(SyncPatch())
    if value == STATUS_CONTRACT_COMPLETED:
        return NeedRevenue(CLOSING, SyncField.STATUS)
    if current.status_key == STATUS_CONTRACT_COMPLETED:
        return AskForecast(catalog.forecast_keys_except(FORECAST_WON), patch)
    return Independent(patch)


def _plan_forecast(current: SyncState, value: str, catalog: CodeCatalog) -> SyncPlan:
    patch = SyncPatch(forecast_key=value)
    if value == current.forecast_key:
        return Independent(SyncPatch())
    if value == FORECAST_WON:
        return NeedRevenue(CLOSING, SyncField.FORECAST)
    options = catalog.status_keys_except(STATUS_CONTRACT_COMPLETED)
    if current.forecast_key == FORECAST_WON:
        return AskStatus(options, None, patch)
    if current.forecast_key == FORECAST_LOST:
        return AskStatus(options, current.status_key, patch)
    return Independent(patch)
