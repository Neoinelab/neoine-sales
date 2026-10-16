"""contacts: 고객·파트너 통합 (P0 M-P0, R2분)

보존 데이터 없음 전제(사용자 결정 2026-10-15). 구 customers·partners와 그것을 참조하던 Deal 및 관련 행은 삭제된다.

Revision ID: 66ebcb3da2da
Revises: c5d8e2f4a916
Create Date: 2026-10-16 08:14:49.147001

expand/contract 원칙의 예외(사용자 결정): contacts 생성, deals의 고객·파트너 FK 재지정, customers·partners drop을
한 리비전에 합친다. 구 앱은 customers·partners 테이블이 없어 이 스키마와 호환되지 않으므로 앱과 같이 배포한다.

순서: contacts 생성 -> deals와 deals를 참조하는 행(deal_actions, deal_stage_changes)과 deals 삭제 ->
구 FK 제거 -> 새 FK 생성 -> customers·partners drop. 점검·중단 로직은 없다. users, codes, bant_labels,
auth_sessions 등은 건드리지 않는다.

downgrade: 구조만 복원한다. customers·partners를 0d248153ec93 시점 구조의 빈 테이블로 다시 만들고 deals FK를 구
이름으로 되돌리며 contacts를 지운다. deals와 그 의존 행은 같은 방식으로 먼저 비운다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "66ebcb3da2da"
down_revision: Union[str, Sequence[str], None] = "c5d8e2f4a916"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NO_SPACE = r"company !~ '\s' and name !~ '\s' and email !~ '\s' and phone !~ '\s'"
# deals를 FK로 참조하는 테이블(자식부터 지운다).
_DEAL_DEPENDENTS = ("deal_actions", "deal_stage_changes")


def _clear_deals() -> None:
    for table in (*_DEAL_DEPENDENTS, "deals"):
        op.execute(f"DELETE FROM {table}")  # noqa: S608


def _create_contacts() -> None:
    op.create_table(
        "contacts",
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind in ('customer', 'partner')", name=op.f("ck_contacts_kind_valid")),
        sa.CheckConstraint(_NO_SPACE, name=op.f("ck_contacts_no_space")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index(
        "ix_contacts_kind_company_lower", "contacts", ["kind", sa.text("lower(company)")]
    )
    op.create_index(
        "ix_contacts_identity",
        "contacts",
        ["kind", sa.text("lower(company)"), sa.text("lower(name)")],
    )
    op.create_index("ix_contacts_created_at_id", "contacts", ["created_at", "id"])


def _create_legacy_tables() -> None:
    op.create_table(
        "customers",
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("contact_name", sa.String(length=100), nullable=False),
        sa.Column("contact_title", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "employee_count is null or employee_count >= 0",
            name=op.f("ck_customers_employee_count_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index("ix_customers_created_at_id", "customers", ["created_at", "id"])
    op.create_table(
        "partners",
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("contact_name", sa.String(length=100), nullable=False),
        sa.Column("contact_title", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partners")),
    )
    op.create_index("ix_partners_created_at_id", "partners", ["created_at", "id"])


def upgrade() -> None:
    """Upgrade schema."""
    _create_contacts()
    _clear_deals()
    op.drop_constraint(op.f("fk_deals_customer_id_customers"), "deals", type_="foreignkey")
    op.drop_constraint(op.f("fk_deals_partner_id_partners"), "deals", type_="foreignkey")
    for column in ("customer_id", "partner_id"):
        op.create_foreign_key(
            op.f(f"fk_deals_{column}_contacts"),
            "deals",
            "contacts",
            [column],
            ["id"],
            ondelete="RESTRICT",
        )
    op.drop_index("ix_partners_created_at_id", table_name="partners")
    op.drop_table("partners")
    op.drop_index("ix_customers_created_at_id", table_name="customers")
    op.drop_table("customers")


def downgrade() -> None:
    """Downgrade schema (구조만 복원, 데이터는 복원하지 않는다)."""
    _clear_deals()
    _create_legacy_tables()
    for column in ("customer_id", "partner_id"):
        op.drop_constraint(op.f(f"fk_deals_{column}_contacts"), "deals", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_deals_customer_id_customers"),
        "deals",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_deals_partner_id_partners"),
        "deals",
        "partners",
        ["partner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_index("ix_contacts_created_at_id", table_name="contacts")
    op.drop_index("ix_contacts_identity", table_name="contacts")
    op.drop_index("ix_contacts_kind_company_lower", table_name="contacts")
    op.drop_table("contacts")
