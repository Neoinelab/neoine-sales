"""deal_model_v2: Deal 원장 재구성 (P1 M-P1)

보존 데이터 없음 전제(사용자 결정 2026-10-15, 2026-10-16). 구 deals와 그것을 참조하던 행(deal_actions,
deal_stage_changes)은 삭제된다.

Revision ID: 7b2e4c9a1d35
Revises: 66ebcb3da2da
Create Date: 2026-10-16 15:30:00.000000

expand/contract 원칙의 예외(사용자 결정): deals를 deal_code PK로 다시 만들고 deal_stage_changes를 drop하며
deal_actions의 FK를 deal_id에서 deal_code로 옮기는 일을 한 리비전에 합친다. 구 앱은 이 스키마와 호환되지
않으므로 앱과 같이 배포한다. 점검·중단 로직은 없다(운영 데이터가 생기면 이 예외는 끝난다).

순서: 의존 행과 deals 삭제 -> deal_stage_changes drop -> deal_actions.deal_id 제거 -> 구 deals drop ->
codes·bant_labels 유니크 제약 -> 새 deals, deal_partners, deal_bant_labels, deal_history ->
deal_actions.deal_code 추가.

downgrade: 구조만 복원한다(데이터는 복원하지 않는다). 새 테이블을 지우고 이전 리비전의 deals,
deal_stage_changes, deal_actions.deal_id 구조를 빈 상태로 되돌린다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7b2e4c9a1d35"
down_revision: Union[str, Sequence[str], None] = "66ebcb3da2da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AMOUNT_MAX = 2**53 - 1
# 리비전은 만들어진 시점의 값을 고정한다(도메인 enum을 import하지 않는다).
_CATEGORIES = (
    "'created', 'status', 'forecast', 'amount', 'expectedClose', 'owner', 'partner', 'contact',"
    " 'bant', 'action', 'attachment', 'other'"
)
_BANT = "'budget', 'authority', 'need', 'timeline'"
_STAGES = (
    "'prospecting', 'introduction', 'poc_preparation', 'poc_completed', 'technical_evaluation',"
    " 'price_negotiation', 'contract_completed', 'lost'"
)


def _clear_deals(*tables: str) -> None:
    """deals와 deals를 참조하는 행을 자식부터 지운다(테이블 이름은 호출하는 곳의 상수다)."""
    for table in tables:
        op.execute(f"DELETE FROM {table}")  # noqa: S608


def _create_deals() -> None:
    op.create_table(
        "deals",
        sa.Column("deal_code", sa.String(length=13), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("solution", sa.String(length=200), nullable=False),
        sa.Column("users", sa.Integer(), nullable=True),
        sa.Column("status_kind", sa.String(length=20), nullable=False),
        sa.Column("status_key", sa.String(length=50), nullable=False),
        sa.Column("forecast_kind", sa.String(length=20), nullable=False),
        sa.Column("forecast_key", sa.String(length=50), nullable=False),
        sa.Column("revenue_amount", sa.BigInteger(), nullable=False),
        sa.Column("revenue_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("quote_submitted", sa.String(length=3), nullable=True),
        sa.Column("quote_submitted_date", sa.Date(), nullable=True),
        sa.Column("poc_state", sa.String(length=3), nullable=True),
        sa.Column("poc_completed_date", sa.Date(), nullable=True),
        sa.Column("procurement", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "deal_code ~ '^[0-9]{8}-[A-Z0-9]{4}$'", name=op.f("ck_deals_code_format")
        ),
        sa.CheckConstraint("users is null or users >= 1", name=op.f("ck_deals_users_positive")),
        sa.CheckConstraint("status_kind = 'status'", name=op.f("ck_deals_status_kind")),
        sa.CheckConstraint("forecast_kind = 'forecast'", name=op.f("ck_deals_forecast_kind")),
        sa.CheckConstraint(
            f"revenue_amount between 1 and {_AMOUNT_MAX}", name=op.f("ck_deals_amount_range")
        ),
        sa.CheckConstraint(
            "(status_key = 'contract_completed') = (forecast_key = 'won')",
            name=op.f("ck_deals_won_sync"),
        ),
        sa.CheckConstraint(
            "quote_submitted is null or quote_submitted in ('YES', 'NO')",
            name=op.f("ck_deals_quote_valid"),
        ),
        sa.CheckConstraint(
            "poc_state is null or poc_state in ('YES', 'ING', 'NO')",
            name=op.f("ck_deals_poc_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["status_kind", "status_key"],
            ["codes.kind", "codes.key"],
            name="fk_deals_status_code",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_kind", "forecast_key"],
            ["codes.kind", "codes.key"],
            name="fk_deals_forecast_code",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_deals_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["contacts.id"],
            name=op.f("fk_deals_customer_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deal_code", name=op.f("pk_deals")),
    )
    for column in (
        "owner_user_id",
        "status_key",
        "forecast_key",
        "revenue_date",
        "updated_at",
        "customer_id",
    ):
        op.create_index(f"ix_deals_{column}", "deals", [column])


def _create_children() -> None:
    op.create_table(
        "deal_partners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_code", sa.String(length=13), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "unlinked_at is null or unlinked_at >= linked_at", name=op.f("ck_deal_partners_period")
        ),
        sa.ForeignKeyConstraint(
            ["deal_code"],
            ["deals.deal_code"],
            name=op.f("fk_deal_partners_deal_code_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            name=op.f("fk_deal_partners_contact_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_partners")),
    )
    op.create_index(
        "uq_deal_partners_one_active",
        "deal_partners",
        ["deal_code"],
        unique=True,
        postgresql_where=sa.text("unlinked_at is null"),
    )
    op.create_index("ix_deal_partners_contact_id", "deal_partners", ["contact_id"])
    op.create_index(
        "ix_deal_partners_deal_code_linked_at", "deal_partners", ["deal_code", "linked_at"]
    )
    op.create_table(
        "deal_bant_labels",
        sa.Column("deal_code", sa.String(length=13), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("label_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            f"category in ({_BANT})", name=op.f("ck_deal_bant_labels_category_valid")
        ),
        sa.ForeignKeyConstraint(
            ["deal_code"],
            ["deals.deal_code"],
            name=op.f("fk_deal_bant_labels_deal_code_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["label_id", "category"],
            ["bant_labels.id", "bant_labels.category"],
            name="fk_deal_bant_labels_label",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deal_code", "category", name=op.f("pk_deal_bant_labels")),
    )
    op.create_index("ix_deal_bant_labels_label_id", "deal_bant_labels", ["label_id"])
    op.create_table(
        "deal_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("deal_code", sa.String(length=13), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("target", sa.String(length=300), nullable=False),
        sa.Column("before_text", sa.Text(), nullable=False),
        sa.Column("after_text", sa.Text(), nullable=False),
        sa.CheckConstraint(f"category in ({_CATEGORIES})", name=op.f("ck_deal_history_category")),
        sa.ForeignKeyConstraint(
            ["deal_code"],
            ["deals.deal_code"],
            name=op.f("fk_deal_history_deal_code_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_deal_history_changed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_history")),
    )
    op.create_index(
        "ix_deal_history_deal_code_changed_at", "deal_history", ["deal_code", "changed_at"]
    )
    op.create_index("ix_deal_history_changed_by_user_id", "deal_history", ["changed_by_user_id"])


def upgrade() -> None:
    """Upgrade schema."""
    _clear_deals("deal_actions", "deal_stage_changes", "deals")
    op.drop_table("deal_stage_changes")  # 인덱스는 테이블과 함께 지워진다
    op.drop_index("ix_deal_actions_deal_id_acted_at", table_name="deal_actions")
    op.drop_constraint(op.f("fk_deal_actions_deal_id_deals"), "deal_actions", type_="foreignkey")
    op.drop_column("deal_actions", "deal_id")
    op.drop_table("deals")
    op.drop_index("uq_codes_kind_key", table_name="codes")
    op.create_unique_constraint("uq_codes_kind_key", "codes", ["kind", "key"])
    op.create_unique_constraint("uq_bant_labels_id_category", "bant_labels", ["id", "category"])
    _create_deals()
    _create_children()
    op.add_column("deal_actions", sa.Column("deal_code", sa.String(length=13), nullable=False))
    op.create_foreign_key(
        op.f("fk_deal_actions_deal_code_deals"),
        "deal_actions",
        "deals",
        ["deal_code"],
        ["deal_code"],
        ondelete="CASCADE",
    )
    op.create_index("ix_deal_actions_deal_code_acted_at", "deal_actions", ["deal_code", "acted_at"])


def _create_old_deals() -> None:
    op.create_table(
        "deals",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("vendor", sa.String(length=100), nullable=False),
        sa.Column("solution", sa.String(length=200), nullable=False),
        sa.Column("revenue_amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("revenue_currency", sa.String(length=3), nullable=False),
        sa.Column("revenue_date", sa.Date(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("partner_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "stage",
            sa.String(length=30),
            server_default=sa.text("'prospecting'"),
            nullable=False,
        ),
        sa.Column("registered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("revenue_amount >= 0", name=op.f("ck_deals_revenue_non_negative")),
        sa.CheckConstraint(f"stage in ({_STAGES})", name=op.f("ck_deals_stage_valid")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["contacts.id"],
            name=op.f("fk_deals_customer_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["contacts.id"],
            name=op.f("fk_deals_partner_id_contacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_deals_owner_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["registered_by_user_id"],
            ["users.id"],
            name=op.f("fk_deals_registered_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deals")),
        sa.UniqueConstraint("code", name=op.f("uq_deals_code")),
    )
    op.create_index("ix_deals_created_at_id", "deals", ["created_at", "id"])
    for column in ("customer_id", "partner_id", "owner_user_id", "registered_by_user_id"):
        op.create_index(f"ix_deals_{column}", "deals", [column])


def _create_old_stage_changes() -> None:
    op.create_table(
        "deal_stage_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage", sa.String(length=30), nullable=False),
        sa.Column("to_stage", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            f"from_stage in ({_STAGES})", name=op.f("ck_deal_stage_changes_from_stage_valid")
        ),
        sa.CheckConstraint(
            f"to_stage in ({_STAGES})", name=op.f("ck_deal_stage_changes_to_stage_valid")
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_stage_changes_deal_id_deals"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_deal_stage_changes_changed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_stage_changes")),
    )
    op.create_index(
        "ix_deal_stage_changes_changed_by_user_id", "deal_stage_changes", ["changed_by_user_id"]
    )
    op.create_index(
        "ix_deal_stage_changes_deal_id_changed_at", "deal_stage_changes", ["deal_id", "changed_at"]
    )


def downgrade() -> None:
    """Downgrade schema (구조만 복원, 데이터는 복원하지 않는다)."""
    _clear_deals("deal_actions", "deals")
    op.drop_index("ix_deal_actions_deal_code_acted_at", table_name="deal_actions")
    op.drop_constraint(op.f("fk_deal_actions_deal_code_deals"), "deal_actions", type_="foreignkey")
    op.drop_column("deal_actions", "deal_code")
    for table in ("deal_history", "deal_bant_labels", "deal_partners"):
        op.drop_table(table)  # 인덱스는 테이블과 함께 지워진다
    op.drop_table("deals")
    op.drop_constraint("uq_bant_labels_id_category", "bant_labels", type_="unique")
    op.drop_constraint("uq_codes_kind_key", "codes", type_="unique")
    op.create_index("uq_codes_kind_key", "codes", ["kind", "key"], unique=True)
    _create_old_deals()
    op.add_column("deal_actions", sa.Column("deal_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        op.f("fk_deal_actions_deal_id_deals"),
        "deal_actions",
        "deals",
        ["deal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_deal_actions_deal_id_acted_at", "deal_actions", ["deal_id", "acted_at"])
    _create_old_stage_changes()
