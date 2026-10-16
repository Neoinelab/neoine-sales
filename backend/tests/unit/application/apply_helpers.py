"""ApplyDealChange 테스트 공용 도우미."""

from datetime import date
from typing import TYPE_CHECKING

from app.application.deal.inputs import DealChangeInput
from app.domain.deal.sync import SyncResolution
from tests.factories_deal import SALES

if TYPE_CHECKING:
    from app.application.deal.dto import ApplyChangeResult, DealView
    from tests.unit.application.deal_env import DealEnv

REVENUE_REQUIRED = "Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다."
CHOICE_REQUIRED = "함께 바꿀 값을 선택하세요."
DAY = date(2026, 10, 20)
CLOSING = SyncResolution(revenue_amount=900_000_000, revenue_date=DAY)


async def apply_change(
    env: DealEnv,
    view: DealView,
    field: str,
    value: object,
    resolution: SyncResolution | None = None,
) -> ApplyChangeResult:
    change = DealChangeInput(field=field, value=value, resolution=resolution)  # type: ignore[arg-type]
    return await env.apply.execute(view.item.deal.id.value, change, SALES)


async def stored_values(env: DealEnv, view: DealView) -> tuple[str, str, int, date]:
    """저장된 (status_key, forecast_key, 매출금액, Expected Close)."""
    deal = await env.uow.deals.get(view.item.deal.id)
    return (
        deal.sync.status_key,
        deal.sync.forecast_key,
        deal.details.revenue_amount.value,
        deal.details.revenue_date,
    )
