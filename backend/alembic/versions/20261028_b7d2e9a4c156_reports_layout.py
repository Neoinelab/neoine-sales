"""reports: 결과 배치 layout 열 추가(순수 expand)

Revision ID: b7d2e9a4c156
Revises: f1c6a8e2b904
Create Date: 2026-10-28 12:00:00.000000

NULL 허용 JSONB 열 1개를 추가한다. 구 앱은 이 열을 모르고 INSERT도 통과하므로 공존·코드 롤백이
안전하다. NULL은 앱이 기본 배치로 읽는다. downgrade는 열을 지운다(저장된 배치 소실).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b7d2e9a4c156"
down_revision: Union[str, Sequence[str], None] = "f1c6a8e2b904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "reports", sa.Column("layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_reports_layout_object"),
        "reports",
        "layout is null or jsonb_typeof(layout) = 'object'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_reports_layout_object"), "reports", type_="check")
    op.drop_column("reports", "layout")
