"""Deal Action 검색의 정렬. 모든 정렬은 단일 쿼리이며 동률 규칙은 방향에 따라 뒤집히지 않는다."""

from typing import TYPE_CHECKING

from sqlalchemy import ColumnElement, case, collate, func

from app.application.ports.deal_action_repository import DealActionSort
from app.domain.deal_action.next_action_status import NextActionStatus
from app.infra.db.models import DealActionRow
from app.infra.db.models_auth import UserRow
from app.infra.db.models_catalog import ActionTypeRow

if TYPE_CHECKING:
    from sqlalchemy import Select


def _status_rank() -> ColumnElement[int]:
    return case(
        {status.value: status.sort_rank for status in NextActionStatus},
        value=DealActionRow.next_action_status,
    )


def _actor_key() -> ColumnElement[str]:
    name = func.coalesce(func.nullif(UserRow.display_name, ""), UserRow.login_id)
    return collate(func.lower(name), "C")


def _type_key() -> ColumnElement[str]:
    return collate(func.lower(ActionTypeRow.name), "C")


def apply_order(
    statement: Select[DealActionRow, str, str], sort: DealActionSort
) -> Select[DealActionRow, str, str]:
    """정렬을 붙인다. 담당자 정렬일 때만 users를 조인한다(퇴사자 포함)."""
    acted_desc = DealActionRow.acted_at.desc()
    tie = (DealActionRow.acted_at.desc(), DealActionRow.id)
    if sort is DealActionSort.ACTED_AT_ASC:
        return statement.order_by(DealActionRow.acted_at.asc(), DealActionRow.id)
    if sort in (DealActionSort.DUE_DATE_ASC, DealActionSort.DUE_DATE_DESC):
        due = DealActionRow.due_date
        due_key = due.asc() if sort is DealActionSort.DUE_DATE_ASC else due.desc()
        return statement.order_by(due_key.nulls_last(), *tie)
    if sort in (DealActionSort.ACTOR_ASC, DealActionSort.ACTOR_DESC):
        joined = statement.join(UserRow, UserRow.id == DealActionRow.actor_user_id)
        actor = _actor_key()
        actor_key = actor.asc() if sort is DealActionSort.ACTOR_ASC else actor.desc()
        return joined.order_by(actor_key, *tie)
    if sort in (DealActionSort.ACTION_TYPE_ASC, DealActionSort.ACTION_TYPE_DESC):
        kind = _type_key()
        type_key = kind.asc() if sort is DealActionSort.ACTION_TYPE_ASC else kind.desc()
        return statement.order_by(type_key, *tie)
    if sort in (DealActionSort.NEXT_ACTION_STATUS_ASC, DealActionSort.NEXT_ACTION_STATUS_DESC):
        rank = _status_rank()
        asc = sort is DealActionSort.NEXT_ACTION_STATUS_ASC
        return statement.order_by((rank.asc() if asc else rank.desc()).nulls_last(), *tie)
    return statement.order_by(acted_desc, DealActionRow.id)
