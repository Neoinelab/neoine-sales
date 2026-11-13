"""business dates: 시각 컬럼 4개를 업무 날짜(date) 컬럼으로 전환

Revision ID: b4d7e2a9c613
Revises: 00c3126aa926
Create Date: 2026-11-13 00:00:00.000000

deal_actions.acted_at -> acted_on(NOT NULL), deal_actions.next_action_closed_at -> next_action_closed_on,
deals.status_changed_at -> status_changed_on(NOT NULL), license_contracts.ended_at -> ended_on.

절차: 새 date 컬럼 추가(NULL) -> 옛 시각을 업무 시간대 날짜로 채움 -> 행 수·NULL 점검(실패하면 중단) ->
NOT NULL·CHECK·인덱스 교체 -> 옛 컬럼 drop. 행은 지우지 않고 시각 정보만 버린다(2026-11-13 사용자 승인).
업무 시간대 = 이 프로세스의 OS 로컬 시간대(migrate 컨테이너가 /etc/localtime을 mount한다).
product 적용은 배포 전 pg_dump 후 사람 승인. 코드만 롤백하면 구 앱이 실패하므로 downgrade를 함께 한다.
downgrade는 날짜를 업무 시간대 00:00으로 되살린다(시각은 복구되지 않는다).
"""

from datetime import datetime, time
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4d7e2a9c613"
down_revision: Union[str, Sequence[str], None] = "00c3126aa926"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCH = 5000
# (테이블, 옛 컬럼, 새 컬럼)
_COLUMNS = (
    ("deal_actions", "acted_at", "acted_on"),
    ("deal_actions", "next_action_closed_at", "next_action_closed_on"),
    ("deals", "status_changed_at", "status_changed_on"),
    ("license_contracts", "ended_at", "ended_on"),
)
_CLOSED_CHECK_NEW = "(coalesce(next_action_status, '') in ('done', 'not_done')) = (next_action_closed_on IS NOT NULL)"
_CLOSED_CHECK_OLD = "((coalesce(next_action_status, '') in ('done', 'not_done')) = (next_action_closed_at IS NOT NULL))"
_ENDED_CHECK_NEW = "((status)::text = 'ended'::text) = (ended_on IS NOT NULL)"
_ENDED_CHECK_OLD = "(((status)::text = 'ended'::text) = (ended_at IS NOT NULL))"


def _convert(table: str, source: str, target: str, convert) -> None:  # type: ignore[no-untyped-def]
    """source 값이 있는 행을 배치로 읽어 convert한 값을 target에 쓴다."""
    bind = op.get_bind()
    last_id = 0
    select = sa.text(
        f"SELECT id, {source} FROM {table} WHERE {source} IS NOT NULL AND id > :last"  # noqa: S608
        f" ORDER BY id LIMIT {_BATCH}"
    )
    update = sa.text(f"UPDATE {table} SET {target} = :value WHERE id = :id")  # noqa: S608
    while True:
        rows = bind.execute(select, {"last": last_id}).all()
        if not rows:
            return
        bind.execute(update, [{"id": row[0], "value": convert(row[1])} for row in rows])
        last_id = rows[-1][0]


def _count(table: str) -> int:
    return int(op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())  # noqa: S608


def _missing(table: str, has: str, lacks: str) -> int:
    sql = f"SELECT count(*) FROM {table} WHERE {has} IS NOT NULL AND {lacks} IS NULL"  # noqa: S608
    return int(op.get_bind().execute(sa.text(sql)).scalar_one())


def upgrade() -> None:
    counts = {table: _count(table) for table in ("deal_actions", "deals", "license_contracts")}
    for table, old, new in _COLUMNS:
        op.add_column(table, sa.Column(new, sa.Date(), nullable=True))
        _convert(table, old, new, lambda value: value.astimezone().date())
    for table, old, new in _COLUMNS:
        if _count(table) != counts[table] or _missing(table, old, new):
            raise RuntimeError(f"{table}.{new} 채움 점검 실패: 행 수 또는 NULL 불일치")

    op.drop_constraint(op.f("ck_deal_actions_next_action_closed_at"), "deal_actions", type_="check")
    op.drop_constraint(
        op.f("ck_license_contracts_ended_has_time"), "license_contracts", type_="check"
    )
    op.drop_index(op.f("ix_deal_actions_acted_at"), table_name="deal_actions")
    op.drop_index(op.f("ix_deal_actions_deal_id_acted_at"), table_name="deal_actions")

    op.alter_column("deal_actions", "acted_on", nullable=False)
    op.alter_column("deals", "status_changed_on", nullable=False)
    op.create_check_constraint(
        op.f("ck_deal_actions_next_action_closed_on"), "deal_actions", _CLOSED_CHECK_NEW
    )
    op.create_check_constraint(
        op.f("ck_license_contracts_ended_has_date"), "license_contracts", _ENDED_CHECK_NEW
    )
    op.create_index(op.f("ix_deal_actions_acted_on"), "deal_actions", ["acted_on"])
    op.create_index(
        op.f("ix_deal_actions_deal_id_acted_on"), "deal_actions", ["deal_id", "acted_on"]
    )
    for table, old, _new in _COLUMNS:
        op.drop_column(table, old)


def downgrade() -> None:
    for table, old, _new in _COLUMNS:
        op.add_column(table, sa.Column(old, sa.DateTime(timezone=True), nullable=True))
    for table, old, new in _COLUMNS:
        _convert(table, new, old, lambda value: datetime.combine(value, time.min).astimezone())
    op.alter_column("deal_actions", "acted_at", nullable=False)
    op.alter_column("deals", "status_changed_at", nullable=False)

    op.drop_constraint(op.f("ck_deal_actions_next_action_closed_on"), "deal_actions", type_="check")
    op.drop_constraint(
        op.f("ck_license_contracts_ended_has_date"), "license_contracts", type_="check"
    )
    op.drop_index(op.f("ix_deal_actions_acted_on"), table_name="deal_actions")
    op.drop_index(op.f("ix_deal_actions_deal_id_acted_on"), table_name="deal_actions")
    op.create_check_constraint(
        op.f("ck_deal_actions_next_action_closed_at"), "deal_actions", _CLOSED_CHECK_OLD
    )
    op.create_check_constraint(
        op.f("ck_license_contracts_ended_has_time"), "license_contracts", _ENDED_CHECK_OLD
    )
    op.create_index(op.f("ix_deal_actions_acted_at"), "deal_actions", ["acted_at"])
    op.create_index(
        op.f("ix_deal_actions_deal_id_acted_at"), "deal_actions", ["deal_id", "acted_at"]
    )
    for table, _old, new in _COLUMNS:
        op.drop_column(table, new)
