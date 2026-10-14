"""사용자 참조 7곳을 users.id(UUID) FK(RESTRICT)로 통일, users 소프트 삭제(퇴사), login_id 유니크 제거

Revision ID: 0d248153ec93
Revises: f4b8d2a6c9e1
Create Date: 2026-10-14 09:54:30.789327

변환(문자열 -> users.id): deals.owner(담당자 이름) -> deals.owner_user_id, deals.owner_user_id(등록자 로그인
id) -> deals.registered_by_user_id, deal_actions.actor -> actor_user_id, deal_stage_changes.changed_by_subject/
changed_by_name -> changed_by_user_id, auth_sessions.subject -> user_id, users.created_by -> created_by_user_id,
directory_settings.updated_by -> updated_by_user_id. users에는 deleted_at, delete_reason(CHECK 2개)이 생기고,
uq_users_login_id(lower(login_id) 유니크)는 유니크가 아닌 ix_users_login_id_lower로 바뀐다(재직자 유일성은
응용 로직이 roster 잠금 안에서 지킨다).

매칭 규칙: 로그인 id 계열은 lower(trim(값)) = lower(login_id). 이름 계열(deals.owner, deal_actions.actor)은
(1) ``-x name_map=<json 경로>``({"이름": "login_id"}) -> (2) login_id 일치 -> (3) lower(trim(display_name))이
유일하게 일치. 동명이인·불일치는 변환 불가. 매칭 로직은 app.infra.db.user_fk_migration_support에 있다.

안전장치(한 트랜잭션, 스키마 변경 이전): 6개 테이블을 ACCESS EXCLUSIVE로 잠근 뒤 변환 불가 데이터를
센다. 하나라도 있으면 데이터를 지우거나 NULL로 바꾸거나 사용자를 만들지 않고 ``<테이블.컬럼>=<건수> (예: ...)``를
담은 RuntimeError로 중단한다(스키마·데이터 불변). 변환 불가 auth_sessions도 기본은 중단하며, 사람이 승인해
``-x drop_orphan_sessions=1``을 줄 때만 그 세션 행을 삭제한다(다른 변환 불가 데이터는 여전히 중단).

호환성(contract, expand/contract 예외): 구 앱·구 프런트는 문자열 컬럼을 읽고 써서 이 스키마와 비호환이다.
앱·프런트·마이그레이션을 같은 배포로 낸다. dev는 main 머지 때 자동 적용되므로, 머지 전에 사람이 dev DB에서
아래 읽기 전용 점검 SQL을 돌려 모두 0건인지 확인한다(자유 입력 owner/actor는 불일치가 많을 수 있다).

  with u as (select lower(login_id) l, lower(trim(display_name)) n from users),
       dn as (select n from u where n is not null group by n having count(*) = 1)
  select 'deals.owner' c, count(*) from deals d
    where not exists (select 1 from u where u.l = lower(trim(d.owner)))
      and not exists (select 1 from dn where dn.n = lower(trim(d.owner)))
  union all select 'deal_actions.actor', count(*) from deal_actions a
    where not exists (select 1 from u where u.l = lower(trim(a.actor)))
      and not exists (select 1 from dn where dn.n = lower(trim(a.actor)))
  union all select 'deals.owner_user_id', count(*) from deals d
    where coalesce(trim(d.owner_user_id), '') <> ''
      and not exists (select 1 from u where u.l = lower(trim(d.owner_user_id)))
  union all select 'deal_stage_changes.changed_by_subject', count(*) from deal_stage_changes c
    where not exists (select 1 from u where u.l = lower(trim(c.changed_by_subject)))
  union all select 'users.created_by', count(*) from users x
    where not exists (select 1 from u where u.l = lower(trim(x.created_by)))
  union all select 'directory_settings.updated_by', count(*) from directory_settings s
    where coalesce(trim(s.updated_by), '') <> ''
      and not exists (select 1 from u where u.l = lower(trim(s.updated_by)))
  union all select 'auth_sessions.subject', count(*) from auth_sessions t
    where not exists (select 1 from u where u.l = lower(trim(t.subject)));

(위 SQL은 name_map을 반영하지 않는다. 0건이 아니면 사용자 등록 또는 name_map 준비가 먼저다.)

롤백: 사용자 확인 후 ``alembic downgrade -1`` + 이전 빌드(앱·프런트) 재배포. downgrade는 문자열 컬럼을 users
조인으로 채우고, 퇴사 처리된 사용자가 있으면(구 스키마에서 되살아나거나 login_id가 겹치므로), 또는 재직자
login_id가 대소문자 무시로 겹치면 아무것도 바꾸지 않고 중단한다. 구 컬럼 길이에 맞춰 이름은 잘릴 수 있다.
product는 적용 전 ``pg_dump`` 백업을 권장한다. 삭제된 세션(drop_orphan_sessions)은 복원되지 않는다.
"""

from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa

from app.infra.db.user_fk_migration_support import (
    SESSIONS,
    Plan,
    build_plan,
    fill_from_mapping,
    guard_downgrade,
    lock_tables,
)


# revision identifiers, used by Alembic.
revision: str = "0d248153ec93"
down_revision: Union[str, Sequence[str], None] = "f4b8d2a6c9e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "users",
    "deals",
    "deal_actions",
    "deal_stage_changes",
    "auth_sessions",
    "directory_settings",
)
_NAME = "coalesce(u.display_name, u.login_id)"


def _seal(table: str, column: str, *, nullable: bool) -> None:
    """NOT NULL, FK(RESTRICT), 인덱스를 확정한다."""
    if not nullable:
        op.alter_column(table, column, nullable=False)
    fk = op.f(f"fk_{table}_{column}_users")
    op.create_foreign_key(fk, table, "users", [column], ["id"], ondelete="RESTRICT")
    op.create_index(f"ix_{table}_{column}", table, [column], unique=False)


def _convert(conn: sa.Connection, plan: Plan, label: str, new: str, *, nullable: bool) -> None:
    """문자열 컬럼(label)을 UUID 컬럼(new)으로 채우고 구 컬럼을 지운 뒤 FK·인덱스를 만든다."""
    table, old = label.split(".")
    op.add_column(table, sa.Column(new, sa.Uuid(), nullable=True))
    fill_from_mapping(conn, table, old, new, plan[label])
    op.drop_column(table, old)
    _seal(table, new, nullable=nullable)


def _users_columns() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("delete_reason", sa.String(length=20), nullable=True))
    reason_ok = "delete_reason is null or delete_reason in ('resigned')"
    op.create_check_constraint(op.f("ck_users_delete_reason_valid"), "users", reason_ok)
    pair = "(deleted_at is null) = (delete_reason is null)"
    op.create_check_constraint(op.f("ck_users_deleted_pair"), "users", pair)
    op.drop_index("uq_users_login_id", table_name="users")
    lowered = [sa.literal_column("lower(login_id)")]
    op.create_index("ix_users_login_id_lower", "users", lowered, unique=False)


def _convert_deals(conn: sa.Connection, plan: Plan) -> None:
    """등록자(구 owner_user_id)와 담당자(구 owner)를 새 컬럼으로 옮긴다. 이름이 겹쳐 순서가 중요하다."""
    op.add_column("deals", sa.Column("registered_by_user_id", sa.Uuid(), nullable=True))
    old_registrant = plan["deals.owner_user_id"]
    fill_from_mapping(conn, "deals", "owner_user_id", "registered_by_user_id", old_registrant)
    op.add_column("deals", sa.Column("owner_user_id_new", sa.Uuid(), nullable=True))
    fill_from_mapping(conn, "deals", "owner", "owner_user_id_new", plan["deals.owner"])
    op.drop_index("ix_deals_owner_user_id", table_name="deals")
    op.drop_column("deals", "owner_user_id")
    op.drop_column("deals", "owner")
    op.alter_column("deals", "owner_user_id_new", new_column_name="owner_user_id")
    _seal("deals", "owner_user_id", nullable=False)
    _seal("deals", "registered_by_user_id", nullable=True)


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    lock_tables(conn, _TABLES)
    plan, orphans = build_plan(conn, context.get_x_argument(as_dictionary=True))
    _users_columns()
    _convert(conn, plan, "users.created_by", "created_by_user_id", nullable=False)
    _convert_deals(conn, plan)
    _convert(conn, plan, "deal_actions.actor", "actor_user_id", nullable=False)
    changed_by = "deal_stage_changes.changed_by_subject"
    _convert(conn, plan, changed_by, "changed_by_user_id", nullable=False)
    op.drop_column("deal_stage_changes", "changed_by_name")
    for raw in orphans:  # 사람이 승인(-x drop_orphan_sessions=1)한 변환 불가 세션만
        conn.execute(sa.text("DELETE FROM auth_sessions WHERE subject = :raw"), {"raw": raw})
    op.drop_index("ix_auth_sessions_subject", table_name="auth_sessions")
    _convert(conn, plan, SESSIONS, "user_id", nullable=False)
    updated_by = "directory_settings.updated_by"
    _convert(conn, plan, updated_by, "updated_by_user_id", nullable=True)


def _restore(
    conn: sa.Connection, label: str, source: str, expression: str, *, size: int = 200
) -> None:
    """구 문자열 컬럼(label)을 만들어 users 조인으로 채운다. NOT NULL은 호출한 쪽이 정한다."""
    table, column = label.split(".")
    op.add_column(table, sa.Column(column, sa.String(length=size), nullable=True))
    join = f"FROM users u WHERE u.id = t.{source}"
    statement = f"UPDATE {table} t SET {column} = {expression} {join}"  # noqa: S608
    conn.execute(sa.text(statement))


def _restore_users(conn: sa.Connection) -> None:
    _restore(conn, "users.created_by", "created_by_user_id", "u.login_id")
    op.alter_column("users", "created_by", nullable=False)
    op.drop_column("users", "created_by_user_id")
    op.drop_constraint(op.f("ck_users_deleted_pair"), "users", type_="check")
    op.drop_constraint(op.f("ck_users_delete_reason_valid"), "users", type_="check")
    op.drop_column("users", "delete_reason")
    op.drop_column("users", "deleted_at")
    op.drop_index("ix_users_login_id_lower", table_name="users")
    lowered = [sa.literal_column("lower(login_id)")]
    op.create_index("uq_users_login_id", "users", lowered, unique=True)


def _restore_deals(conn: sa.Connection) -> None:
    _restore(conn, "deals.owner", "owner_user_id", f"left({_NAME}, 100)", size=100)
    _restore(conn, "deals.registrant_old", "registered_by_user_id", "u.login_id")
    op.alter_column("deals", "owner", nullable=False)
    op.drop_column("deals", "owner_user_id")
    op.drop_column("deals", "registered_by_user_id")
    op.alter_column("deals", "registrant_old", new_column_name="owner_user_id")
    op.create_index("ix_deals_owner_user_id", "deals", ["owner_user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema. 퇴사자·재직자 login_id 중복이 있으면 중단한다(실행은 사용자 확인 후)."""
    conn = op.get_bind()
    lock_tables(conn, _TABLES)
    guard_downgrade(conn)
    _restore_users(conn)
    _restore_deals(conn)
    _restore(conn, "deal_actions.actor", "actor_user_id", f"left({_NAME}, 100)", size=100)
    op.alter_column("deal_actions", "actor", nullable=False)
    op.drop_column("deal_actions", "actor_user_id")
    changes = "deal_stage_changes"
    _restore(conn, f"{changes}.changed_by_subject", "changed_by_user_id", "u.login_id")
    _restore(conn, f"{changes}.changed_by_name", "changed_by_user_id", _NAME)
    op.alter_column(changes, "changed_by_subject", nullable=False)
    op.alter_column(changes, "changed_by_name", nullable=False)
    op.drop_column(changes, "changed_by_user_id")
    _restore(conn, SESSIONS, "user_id", "u.login_id")
    op.alter_column("auth_sessions", "subject", nullable=False)
    op.drop_column("auth_sessions", "user_id")
    op.create_index("ix_auth_sessions_subject", "auth_sessions", ["subject"], unique=False)
    _restore(conn, "directory_settings.updated_by", "updated_by_user_id", "u.login_id")
    op.drop_column("directory_settings", "updated_by_user_id")
