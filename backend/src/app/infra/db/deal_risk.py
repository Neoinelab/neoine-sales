"""경고(기한초과·미업데이트) 판정식의 단일 출처. Deals 목록 필터와 Reports가 함께 쓴다.

compute_risk와 같은 판정: 종결(won·lost) Deal은 경고가 없고, 기한초과는 Open Next Action 중 기한이
오늘보다 앞선 행이 하나라도 있는 경우, 미업데이트는 최종 업데이트가 기준 시각보다 앞이다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, and_, func, select

from app.domain.deal.sync_state import CLOSED_FORECASTS, STATUS_CONTRACT_COMPLETED
from app.domain.deal_action.next_action_status import NextActionStatus
from app.infra.db.deal_derived import last_updated_scalar
from app.infra.db.models import DealActionRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from datetime import date


def not_closed_condition() -> ColumnElement[bool]:
    return DealRow.forecast_key.not_in(sorted(CLOSED_FORECASTS))


def overdue_condition(today: date) -> ColumnElement[bool]:
    return (
        select(DealActionRow.id)
        .where(
            DealActionRow.deal_id == DealRow.id,
            DealActionRow.next_action_status == NextActionStatus.OPEN.value,
            DealActionRow.due_date.is_not(None),
            DealActionRow.due_date < today,
        )
        .correlate(DealRow)
        .exists()
    )


def earliest_open_due_scalar() -> ColumnElement[date | None]:
    """Open Next Action 중 가장 이른 Due(없으면 NULL). 상관 스칼라 서브쿼리."""
    return (
        select(func.min(DealActionRow.due_date))
        .where(
            DealActionRow.deal_id == DealRow.id,
            DealActionRow.next_action_status == NextActionStatus.OPEN.value,
            DealActionRow.due_date.is_not(None),
        )
        .correlate(DealRow)
        .scalar_subquery()
    )


def stale_condition(stale_before: date) -> ColumnElement[bool]:
    return and_(
        DealRow.status_key != STATUS_CONTRACT_COMPLETED,
        last_updated_scalar() < stale_before,
    )
