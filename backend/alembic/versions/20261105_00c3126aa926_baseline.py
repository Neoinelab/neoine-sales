"""baseline: 마이그레이션 이력을 최초 리비전 하나로 통합한 빈 DB 생성 전용 스키마

Revision ID: 00c3126aa926
Revises:
Create Date: 2026-11-05 00:00:00.000000

2026-11-05 이력 통합: 과거 체인 30개(`bb9c1da8d3f9` ... `00c3126aa926`)를 이 리비전 하나로 대체했다.
과거 체인은 커밋 `c4553c0`의 git 이력에 있다. 이 리비전은 **빈 DB에 현재 스키마(테이블 26개)와 기본 시드**
(codes 13, BANT Label 23, Action 유형 8)를 그대로 만드는 용도로만 쓴다.

리비전 id를 직전 head(`00c3126aa926`)와 같게 둔 이유: 이미 이 head인 local·dev DB는 stamp 없이 그대로 쓰고,
통합 전 이미지로 롤백해도 같은 id라 호환된다. head보다 뒤처진 DB는 이 id를 찾지 못해 upgrade가 실패하므로
DB를 새로 만든 뒤 `upgrade head`를 실행한다.

기존 데이터를 지우거나 바꾸지 않는다(2026-11-05 규칙): upgrade는 테이블 생성과 기본 시드 insert만 한다.
과거 리비전의 데이터 변환·삭제는 빈 DB에서 결과가 없으므로 넣지 않았다.

downgrade는 거부한다(아무것도 바꾸기 전에 RuntimeError). 빈 DB가 필요하면 DB를 새로 만든다.

스키마(열 순서·제약 이름·인덱스·ON DELETE 규칙)는 기존 체인을 적용한 DB의 카탈로그와 같게 맞췄다.
시드 값은 tests/fakes/catalog_seed.py·tests/factories_action_type.py와 같아야 한다. id는 넣지 않고
IDENTITY 기본값으로 1부터 매긴다.
"""

from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "00c3126aa926"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DASH = chr(0x2013)
# (key, 이름)
_STATUSES = (
    ("prospecting", "기회발굴"),
    ("introduction", "제품소개"),
    ("poc_preparation", "POC준비"),
    ("poc_completed", "POC완료"),
    ("technical_evaluation", "기술평가"),
    ("price_negotiation", "가격협상"),
    ("contract_completed", "계약완료"),
)
# (key, 이름, outcome, 확률 힌트)
_FORECASTS = (
    ("pipeline", "Pipeline", "open", f"0{_DASH}50"),
    ("best", "Best", "open", f"51{_DASH}75"),
    ("most_likely", "Most Likely", "open", f"75{_DASH}85"),
    ("commit", "Commit", "open", f"85{_DASH}100"),
    ("won", "Won", "won", None),
    ("lost", "Lost", "lost", None),
)
_LABELS = {
    "budget": (
        "단독 예산 확보",
        "풀 예산 확보",
        "잔여 예산 활용",
        "예산 작업중",
        "내년 예산",
        "예산 없음",
        "미확인",
    ),
    "authority": (
        "CEO 보고 완료",
        "CISO 보고 완료",
        "팀장 보고 완료",
        "팀장 검토",
        "담당자 검토",
        "모름",
    ),
    "need": ("보안 사고 발생", "CISO 지시", "보안 강화 요건", "컴플라이언스", "모름"),
    "timeline": ("금년 구매", "POC 후 일정수립", "기술평가만 진행", "내년구매", "미확정"),
}

# 기본 Action 유형(순서 1~8). tests/factories_action_type.py의 기본 유형과 같아야 한다.
_DEFAULT_TYPES = ("통화", "미팅", "이메일", "데모", "제안", "협상", "계약", "기타")


def _create_tables_1() -> None:
    # auth_settings, codes, contacts, forecast_snapshots, forecast_snapshot_columns, login_failures, users, action_types, alert_settings, auth_sessions
    op.create_table(
        "auth_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("(mode in ('ad', 'local'))", name=op.f("ck_auth_settings_mode_valid")),
        sa.CheckConstraint("(id = 1)", name=op.f("ck_auth_settings_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_settings")),
    )
    op.create_table(
        "codes",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("probability_hint", sa.String(length=20), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(((kind)::text <> 'status'::text) OR (probability_hint IS NULL))",
            name=op.f("ck_codes_hint_forecast_only"),
        ),
        sa.CheckConstraint(
            "((key)::text ~ '^[a-z][a-z0-9_]{0,49}$'::text)", name=op.f("ck_codes_key_format")
        ),
        sa.CheckConstraint("(kind in ('status', 'forecast'))", name=op.f("ck_codes_kind_valid")),
        sa.CheckConstraint("(sort_order >= 1)", name=op.f("ck_codes_order_positive")),
        sa.CheckConstraint(
            "(outcome in ('open', 'won', 'lost'))", name=op.f("ck_codes_outcome_valid")
        ),
        sa.CheckConstraint(
            "(((kind)::text <> 'status'::text) OR ((outcome)::text = 'open'::text))",
            name=op.f("ck_codes_status_outcome_open"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codes")),
        sa.UniqueConstraint("kind", "key", name=op.f("uq_codes_kind_key")),
    )
    op.create_index(op.f("ix_codes_kind_sort_order"), "codes", ["kind", "sort_order"], unique=False)
    op.create_index(
        op.f("uq_codes_kind_name_lower"),
        "codes",
        ["kind", sa.text("lower((name)::text)")],
        unique=True,
    )
    op.create_table(
        "contacts",
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind in ('customer', 'partner'))", name=op.f("ck_contacts_kind_valid")
        ),
        sa.CheckConstraint(
            "(((company)::text !~ '\\s'::text) AND ((name)::text !~ '\\s'::text) AND ((email)::text !~ '\\s'::text) AND ((phone)::text !~ '\\s'::text))",
            name=op.f("ck_contacts_no_space"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index(
        op.f("ix_contacts_created_at_id"), "contacts", ["created_at", "id"], unique=False
    )
    op.create_index(
        op.f("ix_contacts_identity"),
        "contacts",
        ["kind", sa.text("lower((company)::text)"), sa.text("lower((name)::text)")],
        unique=False,
    )
    op.create_index(
        op.f("ix_contacts_kind_company_lower"),
        "contacts",
        ["kind", sa.text("lower((company)::text)")],
        unique=False,
    )
    op.create_table(
        "forecast_snapshots",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("snapshot_year", sa.Integer(), nullable=False),
        sa.Column("snapshot_month", sa.Integer(), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((snapshot_month >= 1) AND (snapshot_month <= 12))",
            name=op.f("ck_forecast_snapshots_snapshot_month_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_snapshots")),
        sa.UniqueConstraint(
            "snapshot_year", "snapshot_month", name=op.f("uq_forecast_snapshots_snapshot_year")
        ),
    )
    op.create_table(
        "forecast_snapshot_columns",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("forecast_key", sa.String(length=50), nullable=False),
        sa.Column("forecast_name", sa.String(length=50), nullable=False),
        sa.Column("forecast_outcome", sa.String(length=10), nullable=False),
        sa.Column("forecast_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(forecast_outcome in ('open', 'won', 'lost'))",
            name=op.f("ck_forecast_snapshot_columns_forecast_outcome_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["forecast_snapshots.id"],
            name=op.f("fk_forecast_snapshot_columns_snapshot_id_forecast_snapshots"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_snapshot_columns")),
        sa.UniqueConstraint(
            "snapshot_id", "forecast_key", name=op.f("uq_forecast_snapshot_columns_snapshot_id")
        ),
    )
    op.create_table(
        "login_failures",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("(failures >= 0)", name=op.f("ck_login_failures_failures_non_negative")),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_login_failures")),
    )
    op.create_table(
        "users",
        sa.Column("login_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_reason", sa.String(length=20), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.CheckConstraint(
            "((delete_reason IS NULL) OR ((delete_reason)::text = 'resigned'::text))",
            name=op.f("ck_users_delete_reason_valid"),
        ),
        sa.CheckConstraint(
            "((deleted_at IS NULL) = (delete_reason IS NULL))", name=op.f("ck_users_deleted_pair")
        ),
        sa.CheckConstraint(
            "(role in ('admin', 'sales', 'user'))", name=op.f("ck_users_role_valid")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_users_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_created_at_id"), "users", ["created_at", "id"], unique=False)
    op.create_index(
        op.f("ix_users_created_by_user_id"), "users", ["created_by_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_users_login_id_lower"), "users", [sa.text("lower((login_id)::text)")], unique=False
    )
    op.create_table(
        "action_types",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("default_order", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(is_default = (default_order IS NOT NULL))", name=op.f("ck_action_types_default_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_action_types_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_types")),
    )
    op.create_index(
        op.f("ix_action_types_created_by_user_id"),
        "action_types",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("uq_action_types_name_lower"),
        "action_types",
        [sa.text("lower((name)::text)")],
        unique=True,
    )
    op.create_table(
        "alert_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("stale_days", sa.SmallInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("(id = 1)", name=op.f("ck_alert_settings_single_row")),
        sa.CheckConstraint(
            "((stale_days >= 1) AND (stale_days <= 365))",
            name=op.f("ck_alert_settings_stale_days_range"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_alert_settings_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alert_settings")),
    )
    op.create_index(
        op.f("ix_alert_settings_updated_by_user_id"),
        "alert_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"), "auth_sessions", ["expires_at"], unique=False
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)


def _create_tables_2() -> None:
    # bant_labels, directory_settings, forecast_snapshot_cells, partner_meetings, reports, storage_settings, user_password_hashes, vendors
    op.create_table(
        "bant_labels",
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("default_order", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(category in ('budget', 'authority', 'need', 'timeline'))",
            name=op.f("ck_bant_labels_category_valid"),
        ),
        sa.CheckConstraint(
            "(is_default = (default_order IS NOT NULL))", name=op.f("ck_bant_labels_default_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_bant_labels_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bant_labels")),
        sa.UniqueConstraint("id", "category", name=op.f("uq_bant_labels_id_category")),
    )
    op.create_index(
        op.f("ix_bant_labels_created_by_user_id"),
        "bant_labels",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("uq_bant_labels_category_name_lower"),
        "bant_labels",
        ["category", sa.text("lower((name)::text)")],
        unique=True,
    )
    op.create_table(
        "directory_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("base_dn", sa.String(length=512), nullable=False),
        sa.Column("user_filter", sa.String(length=512), nullable=False),
        sa.Column("connect_timeout_seconds", sa.SmallInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("host", sa.String(length=253), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("security", sa.String(length=16), nullable=False),
        sa.Column("bind_account", sa.String(length=256), nullable=False),
        sa.Column("bind_password_encrypted", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "((connect_timeout_seconds >= 1) AND (connect_timeout_seconds <= 30))",
            name=op.f("ck_directory_settings_connect_timeout_range"),
        ),
        sa.CheckConstraint(
            "((port >= 1) AND (port <= 65535))", name=op.f("ck_directory_settings_port_range")
        ),
        sa.CheckConstraint("(revision >= 1)", name=op.f("ck_directory_settings_revision_positive")),
        sa.CheckConstraint(
            "(security in ('none', 'ssl', 'starttls'))",
            name=op.f("ck_directory_settings_security_values"),
        ),
        sa.CheckConstraint("(id = 1)", name=op.f("ck_directory_settings_single_row")),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_directory_settings_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_directory_settings")),
    )
    op.create_index(
        op.f("ix_directory_settings_updated_by_user_id"),
        "directory_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_table(
        "forecast_snapshot_cells",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=False),
        sa.Column("revenue_year", sa.Integer(), nullable=False),
        sa.Column("revenue_month", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("forecast_key", sa.String(length=50), nullable=False),
        sa.Column("deal_count", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "(amount >= 0)", name=op.f("ck_forecast_snapshot_cells_amount_non_negative")
        ),
        sa.CheckConstraint(
            "(deal_count >= 1)", name=op.f("ck_forecast_snapshot_cells_deal_count_positive")
        ),
        sa.CheckConstraint(
            "((revenue_month >= 1) AND (revenue_month <= 12))",
            name=op.f("ck_forecast_snapshot_cells_revenue_month_range"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_forecast_snapshot_cells_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "forecast_key"],
            ["forecast_snapshot_columns.snapshot_id", "forecast_snapshot_columns.forecast_key"],
            name=op.f("fk_forecast_snapshot_cells_snapshot_id_snapshot_columns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_snapshot_cells")),
        sa.UniqueConstraint(
            "snapshot_id",
            "revenue_year",
            "revenue_month",
            "owner_user_id",
            "forecast_key",
            name=op.f("uq_forecast_snapshot_cells_snapshot_id"),
        ),
    )
    op.create_index(
        op.f("ix_forecast_snapshot_cells_owner_user_id"),
        "forecast_snapshot_cells",
        ["owner_user_id"],
        unique=False,
    )
    op.create_table(
        "partner_meetings",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("partner_company", sa.String(length=200), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(((partner_company)::text <> ''::text) AND ((partner_company)::text !~ '\\s'::text))",
            name=op.f("ck_partner_meetings_company_valid"),
        ),
        sa.CheckConstraint(
            "(content ~ '\\S'::text)", name=op.f("ck_partner_meetings_content_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_partner_meetings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_meetings")),
    )
    op.create_index(
        op.f("ix_partner_meetings_created_by_user_id"),
        "partner_meetings",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_partner_meetings_meeting_date_id"),
        "partner_meetings",
        ["meeting_date", "id"],
        unique=False,
    )
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("generated_sql", sa.Text(), nullable=False),
        sa.Column("chart", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "(jsonb_typeof(definition) = 'object'::text)", name=op.f("ck_reports_definition_object")
        ),
        sa.CheckConstraint(
            "((layout IS NULL) OR (jsonb_typeof(layout) = 'object'::text))",
            name=op.f("ck_reports_layout_object"),
        ),
        sa.CheckConstraint("(revision >= 1)", name=op.f("ck_reports_revision_positive")),
        sa.CheckConstraint(
            "(visibility in ('public', 'private'))", name=op.f("ck_reports_visibility_valid")
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_reports_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_reports_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reports")),
    )
    op.create_index(op.f("ix_reports_owner_user_id"), "reports", ["owner_user_id"], unique=False)
    op.create_index(
        op.f("ix_reports_updated_by_user_id"), "reports", ["updated_by_user_id"], unique=False
    )
    op.create_index(
        op.f("uq_reports_name_lower"), "reports", [sa.text("lower((name)::text)")], unique=True
    )
    op.create_table(
        "storage_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("(id = 1)", name=op.f("ck_storage_settings_single_row")),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_storage_settings_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_settings")),
    )
    op.create_index(
        op.f("ix_storage_settings_updated_by_user_id"),
        "storage_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_table(
        "user_password_hashes",
        sa.Column("user_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_password_hashes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_password_hashes")),
    )
    op.create_table(
        "vendors",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendors")),
    )
    op.create_index(
        op.f("uq_vendors_name_lower"), "vendors", [sa.text("lower((name)::text)")], unique=True
    )


def _create_tables_3() -> None:
    # deals, deal_actions, deal_attachments, deal_bant_labels, deal_history
    op.create_table(
        "deals",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("deal_code", sa.String(length=13), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=False),
        sa.Column("vendor_id", sa.BigInteger(), nullable=True),
        sa.Column("users", sa.Integer(), nullable=False),
        sa.Column("status_kind", sa.String(length=20), nullable=False),
        sa.Column("status_key", sa.String(length=50), nullable=False),
        sa.Column("forecast_kind", sa.String(length=20), nullable=False),
        sa.Column("forecast_key", sa.String(length=50), nullable=False),
        sa.Column("revenue_amount", sa.BigInteger(), nullable=False),
        sa.Column("revenue_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("quote_submitted", sa.String(length=3), nullable=True),
        sa.Column("quote_submitted_date", sa.Date(), nullable=True),
        sa.Column("poc_state", sa.String(length=3), nullable=True),
        sa.Column("poc_completed_date", sa.Date(), nullable=True),
        sa.Column("procurement", sa.String(length=500), nullable=False),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("solution", sa.String(length=200), nullable=False),
        sa.CheckConstraint(
            "((revenue_amount >= 1) AND (revenue_amount <= '9007199254740991'::bigint))",
            name=op.f("ck_deals_amount_range"),
        ),
        sa.CheckConstraint(
            "((deal_code)::text ~ '^[0-9]{8}-[A-Z0-9]{4}$'::text)",
            name=op.f("ck_deals_code_format"),
        ),
        sa.CheckConstraint(
            "((forecast_kind)::text = 'forecast'::text)", name=op.f("ck_deals_forecast_kind")
        ),
        sa.CheckConstraint(
            "((poc_state IS NULL) OR (poc_state in ('YES', 'ING', 'NO')))",
            name=op.f("ck_deals_poc_valid"),
        ),
        sa.CheckConstraint(
            "((quote_submitted IS NULL) OR (quote_submitted in ('YES', 'NO')))",
            name=op.f("ck_deals_quote_valid"),
        ),
        sa.CheckConstraint(
            "((status_kind)::text = 'status'::text)", name=op.f("ck_deals_status_kind")
        ),
        sa.CheckConstraint("(users >= 0)", name=op.f("ck_deals_users_positive")),
        sa.CheckConstraint(
            "(((status_key)::text = 'contract_completed'::text) = ((forecast_key)::text = 'won'::text))",
            name=op.f("ck_deals_won_sync"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["contacts.id"],
            name=op.f("fk_deals_customer_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_kind", "forecast_key"],
            ["codes.kind", "codes.key"],
            name=op.f("fk_deals_forecast_code"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_deals_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["status_kind", "status_key"],
            ["codes.kind", "codes.key"],
            name=op.f("fk_deals_status_code"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_deals_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deals")),
        sa.UniqueConstraint("deal_code", name=op.f("uq_deals_deal_code")),
    )
    op.create_index(op.f("ix_deals_customer_id"), "deals", ["customer_id"], unique=False)
    op.create_index(op.f("ix_deals_forecast_key"), "deals", ["forecast_key"], unique=False)
    op.create_index(op.f("ix_deals_owner_user_id"), "deals", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_deals_revenue_date"), "deals", ["revenue_date"], unique=False)
    op.create_index(op.f("ix_deals_status_key"), "deals", ["status_key"], unique=False)
    op.create_index(op.f("ix_deals_updated_at"), "deals", ["updated_at"], unique=False)
    op.create_index(op.f("ix_deals_vendor_id"), "deals", ["vendor_id"], unique=False)
    op.create_table(
        "deal_actions",
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("action_type_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=False),
        sa.Column("next_action_status", sa.String(length=20), nullable=True),
        sa.Column("next_action_closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "status_kind",
            sa.String(length=20),
            server_default=sa.text("'status'::character varying"),
            nullable=False,
        ),
        sa.Column("status_key", sa.String(length=50), nullable=False),
        sa.Column(
            "forecast_kind",
            sa.String(length=20),
            server_default=sa.text("'forecast'::character varying"),
            nullable=False,
        ),
        sa.Column("forecast_key", sa.String(length=50), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((action IS NOT NULL) OR (next_action IS NOT NULL))",
            name=op.f("ck_deal_actions_action_or_next"),
        ),
        sa.CheckConstraint(
            "((forecast_kind)::text = 'forecast'::text)", name=op.f("ck_deal_actions_forecast_kind")
        ),
        sa.CheckConstraint(
            "((coalesce(next_action_status, '') in ('done', 'not_done')) = (next_action_closed_at IS NOT NULL))",
            name=op.f("ck_deal_actions_next_action_closed_at"),
        ),
        sa.CheckConstraint(
            "(((next_action IS NULL) = (due_date IS NULL)) AND ((next_action IS NULL) = (next_action_status IS NULL)))",
            name=op.f("ck_deal_actions_next_action_fields"),
        ),
        sa.CheckConstraint(
            "(next_action_status in ('open', 'done', 'not_done'))",
            name=op.f("ck_deal_actions_next_action_status"),
        ),
        sa.CheckConstraint(
            "((status_kind)::text = 'status'::text)", name=op.f("ck_deal_actions_status_kind")
        ),
        sa.ForeignKeyConstraint(
            ["action_type_id"],
            ["action_types.id"],
            name=op.f("fk_deal_actions_action_type_id_action_types"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_deal_actions_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_actions_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_kind", "forecast_key"],
            ["codes.kind", "codes.key"],
            name=op.f("fk_deal_actions_forecast_code"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["status_kind", "status_key"],
            ["codes.kind", "codes.key"],
            name=op.f("fk_deal_actions_status_code"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_actions")),
    )
    op.create_index(op.f("ix_deal_actions_acted_at"), "deal_actions", ["acted_at"], unique=False)
    op.create_index(
        op.f("ix_deal_actions_action_type_id"), "deal_actions", ["action_type_id"], unique=False
    )
    op.create_index(
        op.f("ix_deal_actions_actor_user_id"), "deal_actions", ["actor_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_deal_actions_deal_id_acted_at"),
        "deal_actions",
        ["deal_id", "acted_at"],
        unique=False,
    )
    op.create_index(op.f("ix_deal_actions_due_date"), "deal_actions", ["due_date"], unique=False)
    op.create_index(
        op.f("ix_deal_actions_forecast_key"), "deal_actions", ["forecast_key"], unique=False
    )
    op.create_index(
        op.f("ix_deal_actions_status_key"), "deal_actions", ["status_key"], unique=False
    )
    op.create_table(
        "deal_attachments",
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "description",
            sa.String(length=100),
            server_default=sa.text("''::character varying"),
            nullable=False,
        ),
        sa.Column("mime", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=32), nullable=False),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((size_bytes >= 0) AND (size_bytes <= 104857600))",
            name=op.f("ck_deal_attachments_size_range"),
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_attachments_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_deal_attachments_uploaded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_attachments")),
        sa.UniqueConstraint(
            "deal_id", "file_name", name=op.f("uq_deal_attachments_deal_id_file_name")
        ),
        sa.UniqueConstraint("storage_key", name=op.f("uq_deal_attachments_storage_key")),
    )
    op.create_index(
        op.f("ix_deal_attachments_deal_id_uploaded_at"),
        "deal_attachments",
        ["deal_id", "uploaded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deal_attachments_uploaded_by_user_id"),
        "deal_attachments",
        ["uploaded_by_user_id"],
        unique=False,
    )
    op.create_table(
        "deal_bant_labels",
        sa.Column("deal_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("label_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "(category in ('budget', 'authority', 'need', 'timeline'))",
            name=op.f("ck_deal_bant_labels_category_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_bant_labels_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["label_id", "category"],
            ["bant_labels.id", "bant_labels.category"],
            name=op.f("fk_deal_bant_labels_label"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deal_id", "category", name=op.f("pk_deal_bant_labels")),
    )
    op.create_index(
        op.f("ix_deal_bant_labels_label_id"), "deal_bant_labels", ["label_id"], unique=False
    )
    op.create_table(
        "deal_history",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=300), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=False),
        sa.Column("after_text", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "(category in ('created', 'status', 'forecast', 'amount', 'expectedClose', 'owner', 'partner', 'contact', 'bant', 'action', 'attachment', 'other'))",
            name=op.f("ck_deal_history_category"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_deal_history_changed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_history_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_history")),
    )
    op.create_index(
        op.f("ix_deal_history_changed_by_user_id"),
        "deal_history",
        ["changed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_deal_history_deal_id_changed_at"),
        "deal_history",
        ["deal_id", "changed_at"],
        unique=False,
    )


def _create_tables_4() -> None:
    # deal_partners, license_contracts, license_contract_attachments
    op.create_table(
        "deal_partners",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "((unlinked_at IS NULL) OR (unlinked_at >= linked_at))",
            name=op.f("ck_deal_partners_period"),
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_deal_partners_contact_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_partners_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_partners")),
    )
    op.create_index(
        op.f("ix_deal_partners_contact_id"), "deal_partners", ["contact_id"], unique=False
    )
    op.create_index(
        op.f("ix_deal_partners_deal_id_linked_at"),
        "deal_partners",
        ["deal_id", "linked_at"],
        unique=False,
    )
    op.create_index(
        op.f("uq_deal_partners_one_active"),
        "deal_partners",
        ["deal_id"],
        unique=True,
        postgresql_where=sa.text("(unlinked_at IS NULL)"),
    )
    op.create_table(
        "license_contracts",
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("license_start", sa.Date(), nullable=True),
        sa.Column("license_end", sa.Date(), nullable=True),
        sa.Column("term_amount", sa.SmallInteger(), nullable=True),
        sa.Column("term_unit", sa.String(length=10), nullable=True),
        sa.Column(
            "tech_owner",
            sa.String(length=100),
            server_default=sa.text("''::character varying"),
            nullable=False,
        ),
        sa.Column(
            "inspection_cycle",
            sa.String(length=20),
            server_default=sa.text("'none'::character varying"),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), server_default=sa.text("''::text"), nullable=False),
        sa.Column("renewed_from_id", sa.BigInteger(), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((license_start IS NULL) OR (license_end >= license_start))",
            name=op.f("ck_license_contracts_end_after_start"),
        ),
        sa.CheckConstraint(
            "(((status)::text = 'ended'::text) = (ended_at IS NOT NULL))",
            name=op.f("ck_license_contracts_ended_has_time"),
        ),
        sa.CheckConstraint(
            "(inspection_cycle in ('monthly', 'quarterly', 'semiannual', 'yearly', 'none'))",
            name=op.f("ck_license_contracts_inspection_cycle"),
        ),
        sa.CheckConstraint(
            "((NOT (status in ('issued_new', 'issued_renewal'))) OR (license_start IS NOT NULL))",
            name=op.f("ck_license_contracts_issued_has_term"),
        ),
        sa.CheckConstraint(
            "(((status)::text <> 'not_issued'::text) OR (license_start IS NULL))",
            name=op.f("ck_license_contracts_not_issued_no_term"),
        ),
        sa.CheckConstraint(
            "(status in ('not_issued', 'issued_new', 'issued_renewal', 'ended'))",
            name=op.f("ck_license_contracts_status"),
        ),
        sa.CheckConstraint(
            "((term_amount IS NULL) OR ((term_amount >= 1) AND (term_amount <= 99)))",
            name=op.f("ck_license_contracts_term_amount"),
        ),
        sa.CheckConstraint(
            "(((license_start IS NULL) = (license_end IS NULL)) AND ((license_start IS NULL) = (term_amount IS NULL)) AND ((license_start IS NULL) = (term_unit IS NULL)))",
            name=op.f("ck_license_contracts_term_complete"),
        ),
        sa.CheckConstraint(
            "((term_unit IS NULL) OR (term_unit in ('month', 'year')))",
            name=op.f("ck_license_contracts_term_unit"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_license_contracts_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_license_contracts_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["renewed_from_id"],
            ["license_contracts.id"],
            name=op.f("fk_license_contracts_renewed_from_id_license_contracts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_license_contracts_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_license_contracts")),
    )
    op.create_index(
        op.f("ix_license_contracts_created_by_user_id"),
        "license_contracts",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_contracts_deal_id"), "license_contracts", ["deal_id"], unique=False
    )
    op.create_index(
        op.f("ix_license_contracts_license_end_id"),
        "license_contracts",
        ["license_end", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_contracts_renewed_from_id"),
        "license_contracts",
        ["renewed_from_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_contracts_updated_by_user_id"),
        "license_contracts",
        ["updated_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("uq_license_contracts_deal_id_issued"),
        "license_contracts",
        ["deal_id"],
        unique=True,
        postgresql_where=sa.text("(status in ('issued_new', 'issued_renewal'))"),
    )
    op.create_table(
        "license_contract_attachments",
        sa.Column("contract_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "description",
            sa.String(length=100),
            server_default=sa.text("''::character varying"),
            nullable=False,
        ),
        sa.Column("mime", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=32), nullable=False),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "((size_bytes >= 0) AND (size_bytes <= 104857600))",
            name=op.f("ck_license_contract_attachments_size_range"),
        ),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["license_contracts.id"],
            name=op.f("fk_license_contract_attachments_contract_id_license_contracts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_license_contract_attachments_uploaded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_license_contract_attachments")),
        sa.UniqueConstraint(
            "contract_id",
            "file_name",
            name=op.f("uq_license_contract_attachments_contract_id_file_name"),
        ),
        sa.UniqueConstraint(
            "storage_key", name=op.f("uq_license_contract_attachments_storage_key")
        ),
    )
    op.create_index(
        op.f("ix_license_contract_attachments_contract_id_uploaded_at"),
        "license_contract_attachments",
        ["contract_id", "uploaded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_license_contract_attachments_uploaded_by_user_id"),
        "license_contract_attachments",
        ["uploaded_by_user_id"],
        unique=False,
    )


def _seed() -> None:
    now = datetime.now(UTC)
    audit = {"created_at": now, "updated_at": now}
    codes = sa.table(
        "codes",
        sa.column("kind", sa.String()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("outcome", sa.String()),
        sa.column("probability_hint", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = [
        {
            "kind": "status",
            "key": key,
            "name": name,
            "sort_order": index,
            "outcome": "open",
            "probability_hint": None,
            **audit,
        }
        for index, (key, name) in enumerate(_STATUSES, start=1)
    ]
    rows += [
        {
            "kind": "forecast",
            "key": key,
            "name": name,
            "sort_order": index,
            "outcome": outcome,
            "probability_hint": hint,
            **audit,
        }
        for index, (key, name, outcome, hint) in enumerate(_FORECASTS, start=1)
    ]
    op.bulk_insert(codes, rows)
    labels = sa.table(
        "bant_labels",
        sa.column("category", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("default_order", sa.Integer()),
        sa.column("created_by_user_id", sa.BigInteger()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        labels,
        [
            {
                "category": category,
                "name": name,
                "is_default": True,
                "default_order": index,
                "created_by_user_id": None,
                **audit,
            }
            for category, names in _LABELS.items()
            for index, name in enumerate(names, start=1)
        ],
    )
    action_types = sa.table(
        "action_types",
        sa.column("name", sa.String()),
        sa.column("is_default", sa.Boolean()),
        sa.column("default_order", sa.Integer()),
        sa.column("created_by_user_id", sa.BigInteger()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        action_types,
        [
            {
                "name": name,
                "is_default": True,
                "default_order": order,
                "created_by_user_id": None,
                **audit,
            }
            for order, name in enumerate(_DEFAULT_TYPES, start=1)
        ],
    )


def upgrade() -> None:
    """빈 DB에 현재 스키마와 기본 시드를 만든다. 기존 데이터는 지우지 않는다."""
    _create_tables_1()
    _create_tables_2()
    _create_tables_3()
    _create_tables_4()
    _seed()


def downgrade() -> None:
    """되돌릴 수 없다: 아무것도 바꾸기 전에 거부한다."""
    raise RuntimeError(
        "최초 리비전(00c3126aa926)은 되돌릴 수 없습니다. 빈 DB가 필요하면 DB를 새로 만드세요."
    )
