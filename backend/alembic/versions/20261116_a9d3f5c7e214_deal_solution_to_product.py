"""Deal Solution을 Product로 이름 변경: deals.solution -> deals.product

Revision ID: a9d3f5c7e214
Revises: e6b1d4f8a302
Create Date: 2026-11-16 00:00:00.000000

컬럼 이름만 바꾼다(데이터 보존). 이 컬럼에 걸린 CHECK·인덱스는 없다.
코드만 롤백하면 구 앱이 solution 컬럼을 찾지 못하므로 downgrade -1을 함께 한다.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a9d3f5c7e214"
down_revision: Union[str, Sequence[str], None] = "e6b1d4f8a302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("deals", "solution", new_column_name="product")


def downgrade() -> None:
    op.alter_column("deals", "product", new_column_name="solution")
