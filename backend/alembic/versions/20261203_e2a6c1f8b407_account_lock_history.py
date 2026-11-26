from alembic import op
import sqlalchemy as sa

revision = "e2a6c1f8b407"
down_revision = "d8e3f1a7b205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "login_failures",
        sa.Column("had_prior_lock", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("login_failures", "had_prior_lock")
