"""리포트의 Comment 필드 식: 본문을 작성 순(created_at, id)으로 줄바꿈으로 이은 서브쿼리.

Comment가 없으면 NULL이다. 서브쿼리라 JOIN으로 행이 늘지 않아 Deal당 한 번 규칙이 그대로 지켜진다.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Text, func, literal, select
from sqlalchemy.dialects.postgresql import aggregate_order_by

from app.infra.db.models_comment import DealCommentRow
from app.infra.db.report_joins import ACTIONS, DEALS

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

_COMMENTS = DealCommentRow.__table__


def _joined_bodies() -> ColumnElement[str]:
    return func.string_agg(
        _COMMENTS.c.body,
        aggregate_order_by(literal("\n"), _COMMENTS.c.created_at, _COMMENTS.c.id),
        type_=Text,
    )


def deal_comment_text() -> ColumnElement[str]:
    """그 Deal 소속 Comment 전부(Deal Comment + Action Comment)."""
    return (
        select(_joined_bodies())
        .where(_COMMENTS.c.deal_id == DEALS.c.id)
        .correlate(DEALS)
        .scalar_subquery()
    )


def action_comment_text() -> ColumnElement[str]:
    """그 Action에 연결된 Comment만."""
    return (
        select(_joined_bodies())
        .where(_COMMENTS.c.action_id == ACTIONS.c.id)
        .correlate(ACTIONS)
        .scalar_subquery()
    )
