"""Deal Actions 필드 key -> SQL 식 (계획 4.3). 조건용 key 식은 JOIN 없이 Action 열만 쓴다."""

from app.domain.report.catalog import find_field
from app.infra.db.report_fields import FieldSql, option_labels, static_code, user_name
from app.infra.db.report_joins import (
    ACTIONS,
    Joins,
    action_actor,
    action_forecast_code,
    action_status_code,
    action_type,
)


def _plain(column_name: str) -> FieldSql:
    return FieldSql(lambda: ACTIONS.c[column_name])


def _status_labels() -> list[tuple[str, str]]:
    spec = find_field("action.next_action_status")
    return option_labels(spec.options if spec else None)


def action_fields(joins: Joins) -> dict[str, FieldSql]:
    c = ACTIONS.c
    return {
        "action.action": _plain("action"),
        "action.next_action": _plain("next_action"),
        "action.memo": _plain("memo"),
        "action.actor": FieldSql(
            lambda: c.actor_user_id, value=lambda: user_name(action_actor(joins))
        ),
        "action.type": FieldSql(lambda: c.action_type_id, value=lambda: action_type(joins).c.name),
        "action.next_action_status": static_code(lambda: c.next_action_status, _status_labels()),
        "action.status": FieldSql(
            lambda: c.status_key,
            value=lambda: action_status_code(joins).c.name,
            order=lambda: action_status_code(joins).c.sort_order,
        ),
        "action.forecast": FieldSql(
            lambda: c.forecast_key,
            value=lambda: action_forecast_code(joins).c.name,
            order=lambda: action_forecast_code(joins).c.sort_order,
        ),
        "action.due_date": _plain("due_date"),
        "action.acted_at": _plain("acted_at"),
        "action.closed_at": _plain("next_action_closed_at"),
        "action.count": FieldSql(lambda: c.id),
    }
