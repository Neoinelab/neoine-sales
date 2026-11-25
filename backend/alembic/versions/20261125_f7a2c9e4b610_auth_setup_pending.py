import sqlalchemy as sa
from alembic import op

revision = "f7a2c9e4b610"
down_revision = "c5e9a2f7d104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_settings",
        sa.Column("setup_pending", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("auth_settings", "setup_pending")
