import sqlalchemy as sa
from alembic import op

revision = "a4d8e2c6f901"
down_revision = "f7a2c9e4b610"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_settings",
        sa.Column("admin_setup_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("auth_settings", "admin_setup_pending")
