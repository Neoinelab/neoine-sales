"""create customers partners deals

Revision ID: bb9c1da8d3f9
Revises:
Create Date: 2026-10-07 10:41:57.973836

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "bb9c1da8d3f9"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "employee_count is null or employee_count >= 0",
            name=op.f("ck_customers_employee_count_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
    )
    op.create_index("ix_customers_created_at_id", "customers", ["created_at", "id"], unique=False)
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partners")),
    )
    op.create_index("ix_partners_created_at_id", "partners", ["created_at", "id"], unique=False)
    op.create_table(
        "deals",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(length=100), nullable=False),
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
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revenue_amount >= 0", name=op.f("ck_deals_revenue_non_negative")),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_deals_customer_id_customers"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["partner_id"],
            ["partners.id"],
            name=op.f("fk_deals_partner_id_partners"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deals")),
        sa.UniqueConstraint("code", name=op.f("uq_deals_code")),
    )
    op.create_index("ix_deals_created_at_id", "deals", ["created_at", "id"], unique=False)
    op.create_index("ix_deals_customer_id", "deals", ["customer_id"], unique=False)
    op.create_index("ix_deals_partner_id", "deals", ["partner_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_deals_partner_id", table_name="deals")
    op.drop_index("ix_deals_customer_id", table_name="deals")
    op.drop_index("ix_deals_created_at_id", table_name="deals")
    op.drop_table("deals")
    op.drop_index("ix_partners_created_at_id", table_name="partners")
    op.drop_table("partners")
    op.drop_index("ix_customers_created_at_id", table_name="customers")
    op.drop_table("customers")
