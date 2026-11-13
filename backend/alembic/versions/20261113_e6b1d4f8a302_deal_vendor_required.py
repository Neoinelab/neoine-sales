"""Deal Vendor 필수: deals.vendor_id를 NOT NULL로 변경

Revision ID: e6b1d4f8a302
Revises: c8e3f1a7d295
Create Date: 2026-11-13 00:00:00.000000

upgrade는 Vendor 없는 Deal이 있으면 건수와 code를 알리고 중단한다(행·값은 지우거나 채우지 않는다).
없으면 NOT NULL만 건다. downgrade는 NOT NULL만 푼다. 코드만 롤백해도 하위 호환이다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6b1d4f8a302"
down_revision: Union[str, Sequence[str], None] = "c8e3f1a7d295"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    codes = (
        bind.execute(
            sa.text("SELECT deal_code FROM deals WHERE vendor_id IS NULL ORDER BY deal_code")
        )
        .scalars()
        .all()
    )
    if codes:
        raise RuntimeError(
            f"Vendor가 없는 Deal이 {len(codes)}건 있어 deals.vendor_id를 NOT NULL로 바꿀 수 없습니다. "
            "먼저 이 Deal들에 Vendor를 지정하세요: " + ", ".join(codes)
        )
    op.alter_column("deals", "vendor_id", existing_type=sa.BigInteger(), nullable=False)


def downgrade() -> None:
    op.alter_column("deals", "vendor_id", existing_type=sa.BigInteger(), nullable=True)
