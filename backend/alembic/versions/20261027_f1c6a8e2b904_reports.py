"""reports: 저장 리포트 테이블 추가(순수 expand)

Revision ID: f1c6a8e2b904
Revises: d4b8f6a2c013
Create Date: 2026-10-27 12:00:00.000000

기존 테이블·컬럼을 건드리지 않고 reports 1개만 추가한다. 구 앱과 공존 가능하고 코드만 롤백해도
안전하다(구 앱은 이 테이블을 모른다). downgrade는 테이블을 지운다(저장 리포트 소실).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f1c6a8e2b904"
down_revision: Union[str, Sequence[str], None] = "d4b8f6a2c013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
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
        sa.CheckConstraint(
            "visibility in ('public', 'private')", name=op.f("ck_reports_visibility_valid")
        ),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_reports_revision_positive")),
        sa.CheckConstraint(
            "jsonb_typeof(definition) = 'object'", name=op.f("ck_reports_definition_object")
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
    op.create_index(
        "uq_reports_name_lower",
        "reports",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index("ix_reports_owner_user_id", "reports", ["owner_user_id"])
    op.create_index("ix_reports_updated_by_user_id", "reports", ["updated_by_user_id"])


def downgrade() -> None:
    """Downgrade schema. 저장 리포트가 모두 사라진다."""
    op.drop_index("ix_reports_updated_by_user_id", table_name="reports")
    op.drop_index("ix_reports_owner_user_id", table_name="reports")
    op.drop_index("uq_reports_name_lower", table_name="reports")
    op.drop_table("reports")
