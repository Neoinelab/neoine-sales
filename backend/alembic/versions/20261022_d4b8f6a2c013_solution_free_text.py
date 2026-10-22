"""solution_free_text: Solution 관리 목록을 없애고 deals.solution 텍스트로 바꾼다

Revision ID: d4b8f6a2c013
Revises: 11bfe225caf5
Create Date: 2026-10-22 10:00:00.000000

expand/contract 원칙의 예외(사용자 승인, 앱과 같은 배포 전제):
deals.solution(varchar 200, NOT NULL, 기본값 없음)을 추가하고 기존 Solution 이름을 옮긴 뒤
(Solution이 없던 Deal은 빈 문자열) solutions 테이블과 deals.solution_id·복합 FK·CHECK·인덱스를
한 리비전에서 지운다. 구 앱은 solution_id를 읽다 실패하므로 코드만 롤백하면 안 되고
롤백 시 downgrade -1을 함께 실행해야 한다. 어느 Deal에도 쓰이지 않은 Solution 이름은 사라진다.
downgrade는 구조(열·제약 이름·인덱스)만 되살리고 solutions는 비어 있으며 텍스트 값은 버린다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4b8f6a2c013"
down_revision: Union[str, Sequence[str], None] = "11bfe225caf5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("deals", sa.Column("solution", sa.String(length=200), nullable=True))
    op.execute(
        "UPDATE deals SET solution = solutions.name FROM solutions "
        "WHERE deals.solution_id = solutions.id"
    )
    op.execute("UPDATE deals SET solution = '' WHERE solution IS NULL")
    op.alter_column("deals", "solution", existing_type=sa.String(length=200), nullable=False)
    op.drop_index("ix_deals_solution_id", table_name="deals")
    op.drop_constraint(op.f("fk_deals_solution"), "deals", type_="foreignkey")
    op.drop_constraint(op.f("ck_deals_solution_needs_vendor"), "deals", type_="check")
    op.drop_column("deals", "solution_id")
    op.drop_index("uq_solutions_vendor_id_name_lower", table_name="solutions")
    op.drop_table("solutions")


def downgrade() -> None:
    """Downgrade schema. 텍스트 값은 버리고 빈 solutions와 NULL solution_id를 되살린다."""
    op.create_table(
        "solutions",
        sa.Column("vendor_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
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
    op.add_column("deals", sa.Column("solution_id", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_deals_solution_needs_vendor"),
        "deals",
        "solution_id is null or vendor_id is not null",
    )
    op.create_foreign_key(
        op.f("fk_deals_solution"),
        "deals",
        "solutions",
        ["solution_id", "vendor_id"],
        ["id", "vendor_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_deals_solution_id", "deals", ["solution_id"], unique=False)
    op.drop_column("deals", "solution")
