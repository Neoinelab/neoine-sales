"""Deal 목록의 파생값: last_updated_at, Next Action 기준 행.

last_updated_at = 모든 Action 중 가장 최근 acted_at(없으면 Deal 등록 시각, Deal 수정은 무시).
next_action 요약과 상태·기한초과 판정의 기준 행 = Next Action이 있는 가장 최근 Action.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, func, select

from app.infra.db.models import DealActionRow
from app.infra.db.models_deal import DealRow

if TYPE_CHECKING:
    from datetime import datetime

# Deal별 모든 Action 중 가장 최근 수행 시각(진행사항만 있는 행 포함).
LATEST_ACTED = (
    select(
        DealActionRow.deal_id.label("deal_id"),
        func.max(DealActionRow.acted_at).label("acted_at"),
    )
    .group_by(DealActionRow.deal_id)
    .subquery("latest_acted")
)

# Next Action이 있는 Action 중 가장 최근 행(acted_at, id 내림차순 첫 행)만 남기는 부분 질의.
_RANKED = (
    select(
        DealActionRow.deal_id.label("deal_id"),
        DealActionRow.next_action.label("next_action"),
        DealActionRow.due_date.label("due_date"),
        DealActionRow.next_action_status.label("next_action_status"),
        func.row_number()
        .over(
            partition_by=DealActionRow.deal_id,
            order_by=(DealActionRow.acted_at.desc(), DealActionRow.id.desc()),
        )
        .label("position"),
    )
    .where(DealActionRow.next_action.is_not(None))
    .subquery("ranked_next_actions")
)
LATEST_NEXT = select(_RANKED).where(_RANKED.c.position == 1).subquery("latest_next_action")

LAST_UPDATED = func.coalesce(LATEST_ACTED.c.acted_at, DealRow.created_at)


def last_updated_scalar() -> ColumnElement[datetime]:
    """LAST_UPDATED와 같은 값을 조인 없이 계산하는 상관 스칼라 서브쿼리(count가 조건만 쓴다)."""
    latest = (
        select(func.max(DealActionRow.acted_at))
        .where(DealActionRow.deal_id == DealRow.id)
        .correlate(DealRow)
        .scalar_subquery()
    )
    return func.coalesce(latest, DealRow.created_at)
