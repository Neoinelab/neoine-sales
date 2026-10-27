"""`deal.risk`·`deal.status_days`의 SQL. Deals 목록과 같은 판정(`compute_risk`)."""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    Integer,
    and_,
    case,
    cast,
    false,
    func,
    literal,
    null,
    or_,
    type_coerce,
)

from app.infra.db.deal_risk import not_closed_condition, overdue_condition, stale_condition
from app.infra.db.report_buckets import local_time
from app.infra.db.report_joins import DEALS

if TYPE_CHECKING:
    from app.domain.report.resolve import ReportContext
    from app.infra.db.report_fields import Expr

OVERDUE = "overdue"
STALE = "stale"
OVERDUE_STALE = "overdue_stale"


class RiskExprs:
    """종결 여부·기한초과·미업데이트 판정식(조건과 값 식이 함께 쓴다)."""

    def __init__(self, context: ReportContext) -> None:
        self.not_closed = not_closed_condition()
        self.overdue = overdue_condition(context.today)
        self.stale = stale_condition(context.risk.stale_before())

    def flagged(self, keys: set[str]) -> Expr:
        """종결이 아니면서 고른 경고(기한초과·미업데이트)에 해당하는가. 고른 것이 없으면 거짓."""
        chosen: list[Expr] = []
        if OVERDUE in keys:
            chosen.append(self.overdue)
        if STALE in keys:
            chosen.append(self.stale)
        return and_(self.not_closed, or_(*chosen)) if chosen else false()

    def value(self) -> Expr:
        """결과 값: overdue_stale / overdue / stale / NULL(종결이거나 경고 없음)."""
        return case(
            (~self.not_closed, null()),
            (and_(self.overdue, self.stale), literal(OVERDUE_STALE)),
            (self.overdue, literal(OVERDUE)),
            (self.stale, literal(STALE)),
            else_=null(),
        )


def status_days(context: ReportContext) -> Expr:
    """현재 Status에 머문 업무 날짜 수(음수면 0). 시각은 업무 오프셋의 날짜로 바꿔 센다."""
    changed_on = cast(local_time(DEALS.c.status_changed_at, context), Date)
    return func.greatest(type_coerce(literal(context.today) - changed_on, Integer), 0)
