"""Status·Forecast 단일 변경의 적용: `ApplyDealChange`와 Action 등록이 함께 쓰는 협력자."""

from typing import TYPE_CHECKING

from app.domain.code.values import CodeKind
from app.domain.deal.errors import UnknownCodeError
from app.domain.deal.sync import (
    CodeCatalog,
    CodeName,
    SyncApplied,
    SyncChange,
    SyncField,
    SyncState,
    finalize_plan,
    plan_change,
)

if TYPE_CHECKING:
    from app.application.ports.unit_of_work import UnitOfWork
    from app.domain.deal.entities import Deal
    from app.domain.deal.sync import SyncResolution


async def load_catalog(uow: UnitOfWork) -> CodeCatalog:
    """Status·Forecast 코드 목록을 종류당 한 번씩 읽는다."""
    return CodeCatalog(
        statuses=tuple(
            CodeName(c.key.value, c.name) for c in await uow.codes.list(CodeKind.STATUS)
        ),
        forecasts=tuple(
            CodeName(c.key.value, c.name) for c in await uow.codes.list(CodeKind.FORECAST)
        ),
    )


def _known(catalog: CodeCatalog, field: SyncField, value: object) -> str:
    keys = catalog.statuses if field is SyncField.STATUS else catalog.forecasts
    if not isinstance(value, str) or all(code.key != value for code in keys):
        raise UnknownCodeError
    return value


def apply_sync_change(
    deal: Deal,
    field: str,
    value: object,
    resolution: SyncResolution | None,
    catalog: CodeCatalog,
) -> SyncApplied:
    """동기화 규칙에 따라 Deal의 Status/Forecast를 바꾼다(함께 바뀌는 값 포함, 저장은 호출자)."""
    sync_field = SyncField(field)
    target = _known(catalog, sync_field, value)
    current = SyncState(deal.sync.status_key, deal.sync.forecast_key)
    plan = plan_change(current, SyncChange(sync_field, target), catalog)
    applied = finalize_plan(current, plan, resolution, catalog)
    deal.apply_sync(applied)
    return applied
