"""alert_settings: 경고 기준 설정과 deals.status_changed_at (P3 M-P3)

Revision ID: a4d7e1b92c06
Revises: c2699d3627ff
Create Date: 2026-10-17 10:00:00.000000

expand: 새 테이블 1개와 deals 컬럼 1개(nullable로 추가 -> created_at으로 채움 -> NOT NULL).
행은 지우지 않는다. alert_settings는 시드 없음(저장 전에는 앱의 기본값 14일).
downgrade는 컬럼과 테이블만 제거한다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4d7e1b92c06"
down_revision: Union[str, Sequence[str], None] = "c2699d3627ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "alert_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("stale_days", sa.SmallInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_alert_settings_single_row")),
        sa.CheckConstraint(
            "stale_days BETWEEN 1 AND 365", name=op.f("ck_alert_settings_stale_days_range")
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
        "ix_alert_settings_updated_by_user_id",
        "alert_settings",
        ["updated_by_user_id"],
        unique=False,
    )
    op.add_column(
        "deals", sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE deals SET status_changed_at = created_at")
    op.alter_column("deals", "status_changed_at", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("deals", "status_changed_at")
    op.drop_index("ix_alert_settings_updated_by_user_id", table_name="alert_settings")
    op.drop_table("alert_settings")
