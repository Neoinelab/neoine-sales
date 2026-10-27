"""경고(기한초과·미업데이트) 판정식의 단일 출처. Deals 목록 필터와 Reports가 함께 쓴다.

compute_risk와 같은 판정: 종결(won·lost) Deal은 경고가 없고, 기한초과는 Next Action 기준 행의
기한이 오늘보다 앞, 미업데이트는 최종 업데이트가 기준 시각보다 앞이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, select

from app.domain.deal.sync_state import CLOSED_FORECASTS
from app.infra.db.deal_derived import LATEST_NEXT, last_updated_scalar
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from datetime import date, datetime


def not_closed_condition() -> ColumnElement[bool]:
    return DealRow.forecast_key.not_in(sorted(CLOSED_FORECASTS))


def overdue_condition(today: date) -> ColumnElement[bool]:
    return (
        select(LATEST_NEXT.c.deal_id)
        .where(LATEST_NEXT.c.deal_id == DealRow.id, LATEST_NEXT.c.due_date < today)
        .correlate(DealRow)
        .exists()
    )


def stale_condition(stale_before: datetime) -> ColumnElement[bool]:
    return last_updated_scalar() < stale_before
