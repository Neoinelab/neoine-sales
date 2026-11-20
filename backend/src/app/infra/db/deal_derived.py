"""Deal 목록의 파생값: last_updated_on, Next Action 기준 행.

last_updated_on = 모든 Action 중 가장 늦은 acted_on(없으면 Deal 등록일, Deal 수정은 무시).
등록일 = created_at을 업무 오프셋(서버 OS 시간대, 요청 시점)의 날짜로 바꾼 값.
next_action 요약의 기준 행은 `latest_next(today)`(지난 Open 우선, RK-R1).
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Date,
    Subquery,
    and_,
    case,
    cast,
    func,
    literal,
    literal_column,
    select,
)

from app.domain.deal_action.next_action_status import NextActionStatus
from app.infra.db.models import DealActionRow
from app.infra.db.models_deal import DealRow

# Deal별 모든 Action 중 가장 최근 수행 시각(진행사항만 있는 행 포함).
LATEST_ACTED = (
    select(
        DealActionRow.deal_id.label("deal_id"),
        func.max(DealActionRow.acted_on).label("acted_on"),
    )
    .group_by(DealActionRow.deal_id)
    .subquery("latest_acted")
)


def basis_order(today: date) -> tuple[ColumnElement[Any], ...]:
    """Next Action 기준 행 정렬(첫 행이 기준 행). `latest_next`와 단건 조회가 함께 쓴다."""
    overdue = and_(
        DealActionRow.next_action_status == NextActionStatus.OPEN.value,
        DealActionRow.due_date < today,
    )
    return (
        case((overdue, 0), else_=1),
        case((overdue, DealActionRow.due_date)).asc(),
        case((overdue, None), else_=DealActionRow.acted_on).desc().nulls_last(),
        DealActionRow.id.desc(),
    )


def latest_next(today: date) -> Subquery:
    """Deal별 Next Action 기준 행(RK-R1, domain `pick_next_action_basis`와 같은 정의).

    지난 Open(상태 open, due_date < today)이 있으면 Due가 가장 이른 행(같으면 id 큰 행),
    없으면 acted_on 내림차순·id 내림차순 첫 Next Action 행. Next Action이 있는 행만 순위를 매긴다.
    """
    ranked = (
        select(
            DealActionRow.id.label("action_id"),
            DealActionRow.deal_id.label("deal_id"),
            DealActionRow.next_action.label("next_action"),
            DealActionRow.due_date.label("due_date"),
            DealActionRow.next_action_status.label("next_action_status"),
            func.row_number()
            .over(
                partition_by=DealActionRow.deal_id,
                order_by=basis_order(today),
            )
            .label("position"),
        )
        .where(DealActionRow.next_action.is_not(None))
        .subquery("ranked_next_actions")
    )
    return select(ranked).where(ranked.c.position == 1).subquery("latest_next_action")


_ONE_SECOND: ColumnElement[object] = literal_column("interval '1 second'")


def server_utc_offset() -> timedelta:
    """요청 시점의 서버 OS 시간대 UTC 오프셋(업무 오프셋)."""
    return datetime.now().astimezone().utcoffset() or timedelta(0)


def registered_on(offset: timedelta | None = None) -> ColumnElement[date]:
    """Deal 등록일: created_at(timestamptz)을 업무 오프셋의 날짜로 바꾼다."""
    seconds = (server_utc_offset() if offset is None else offset).total_seconds()
    return cast(func.timezone(literal(seconds) * _ONE_SECOND, DealRow.created_at), Date)


LAST_UPDATED = func.coalesce(LATEST_ACTED.c.acted_on, registered_on())


def last_updated_scalar(offset: timedelta | None = None) -> ColumnElement[date]:
    """LAST_UPDATED와 같은 값을 조인 없이 계산하는 상관 스칼라 서브쿼리(count가 조건만 쓴다)."""
    latest = (
        select(func.max(DealActionRow.acted_on))
        .where(DealActionRow.deal_id == DealRow.id)
        .correlate(DealRow)
        .scalar_subquery()
    )
    return func.coalesce(latest, registered_on(offset))
