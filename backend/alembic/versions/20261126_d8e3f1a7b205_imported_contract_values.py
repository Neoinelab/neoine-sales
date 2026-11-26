"""가져온 계약의 미상 금액·수량과 회사명 공백을 보존한다."""

from alembic import op
import sqlalchemy as sa

revision = "d8e3f1a7b205"
down_revision = "b6e1f8a3d902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("deals", "users", existing_type=sa.Integer(), nullable=True)
    op.alter_column("deals", "revenue_amount", existing_type=sa.BigInteger(), nullable=True)
    op.drop_constraint(op.f("ck_contacts_no_space"), "contacts", type_="check")
    op.create_check_constraint(
        op.f("ck_contacts_no_space"),
        "contacts",
        r"name !~ '\s' and email !~ '\s' and phone !~ '\s'",
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM deals WHERE users IS NULL OR revenue_amount IS NULL) "
        r"OR EXISTS (SELECT 1 FROM contacts WHERE company ~ '\s') THEN "
        "RAISE EXCEPTION 'Imported values prevent lossless downgrade'; "
        "END IF; END $$"
    )
    op.alter_column("deals", "users", existing_type=sa.Integer(), nullable=False)
    op.alter_column("deals", "revenue_amount", existing_type=sa.BigInteger(), nullable=False)
    op.drop_constraint(op.f("ck_contacts_no_space"), "contacts", type_="check")
    op.create_check_constraint(
        op.f("ck_contacts_no_space"),
        "contacts",
        r"company !~ '\s' and name !~ '\s' and email !~ '\s' and phone !~ '\s'",
    )
