"""vendors, solutions: Vendor·Solution 관리 목록과 Deal 연동

Revision ID: 7a185add9ec4
Revises: a4d7e1b92c06
Create Date: 2026-10-19 12:46:16.368552

expand/contract 원칙의 예외(사용자 승인, 보존 데이터 없음, 앱과 같은 배포 전제):
새 테이블 2개와 deals.vendor_id/solution_id(NULL 허용)를 만들고 deals.vendor/solution
텍스트 컬럼은 값을 옮기지 않고 버린다. 기존 Deal은 vendor_id·solution_id가 NULL이 된다.
downgrade는 텍스트 컬럼을 빈 문자열로 되살리고 새 컬럼·테이블을 지운다(값은 복원되지 않는다).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a185add9ec4"
down_revision: Union[str, Sequence[str], None] = "a4d7e1b92c06"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "vendors",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendors")),
    )
    op.create_index(
        "uq_vendors_name_lower", "vendors", [sa.literal_column("lower(name)")], unique=True
    )
    op.create_table(
        "solutions",
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_solutions_vendor_id_vendors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solutions")),
        sa.UniqueConstraint("id", "vendor_id", name="uq_solutions_id_vendor_id"),
    )
    op.create_index(
        "uq_solutions_vendor_id_name_lower",
        "solutions",
        ["vendor_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.add_column("deals", sa.Column("vendor_id", sa.Uuid(), nullable=True))
    op.add_column("deals", sa.Column("solution_id", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        op.f("ck_deals_solution_needs_vendor"),
        "deals",
        "solution_id is null or vendor_id is not null",
    )
    op.create_foreign_key(
        op.f("fk_deals_vendor_id_vendors"),
        "deals",
        "vendors",
        ["vendor_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        op.f("fk_deals_solution"),
        "deals",
        "solutions",
        ["solution_id", "vendor_id"],
        ["id", "vendor_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_deals_vendor_id", "deals", ["vendor_id"], unique=False)
    op.create_index("ix_deals_solution_id", "deals", ["solution_id"], unique=False)
    op.drop_column("deals", "solution")
    op.drop_column("deals", "vendor")


def downgrade() -> None:
    """Downgrade schema. 텍스트 값은 복원하지 않고 빈 문자열로 채운다."""
    op.add_column(
        "deals",
        sa.Column("vendor", sa.String(length=100), nullable=False, server_default=""),
    )
    op.add_column(
        "deals",
        sa.Column("solution", sa.String(length=200), nullable=False, server_default=""),
    )
    op.alter_column("deals", "vendor", server_default=None)
    op.alter_column("deals", "solution", server_default=None)
    op.drop_index("ix_deals_solution_id", table_name="deals")
    op.drop_index("ix_deals_vendor_id", table_name="deals")
    op.drop_constraint(op.f("fk_deals_solution"), "deals", type_="foreignkey")
    op.drop_constraint(op.f("fk_deals_vendor_id_vendors"), "deals", type_="foreignkey")
    op.drop_constraint(op.f("ck_deals_solution_needs_vendor"), "deals", type_="check")
    op.drop_column("deals", "solution_id")
    op.drop_column("deals", "vendor_id")
    op.drop_index("uq_solutions_vendor_id_name_lower", table_name="solutions")
    op.drop_table("solutions")
    op.drop_index("uq_vendors_name_lower", table_name="vendors")
    op.drop_table("vendors")
