from alembic import op

revision = "b6e1f8a3d902"
down_revision = "a4d8e2c6f901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE directory_settings SET bind_account = NULL, bind_password_encrypted = NULL"
    )


def downgrade() -> None:
    pass
