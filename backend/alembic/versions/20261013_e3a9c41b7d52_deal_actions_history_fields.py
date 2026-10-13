"""deal_actions 이력 필드: title/content 개명, next_action/due_date 추가, 소프트 삭제 행 정리

Revision ID: e3a9c41b7d52
Revises: dd7f21f7190e
Create Date: 2026-10-13 10:00:00.000000

호환성: 이 리비전은 구 앱(title/content 사용)과 호환되지 않는다(컬럼 개명).
앱과 마이그레이션을 같은 배포에서 함께 적용해야 한다. 소프트 삭제된 활동 행은 물리 삭제되어
downgrade로 복원되지 않는다. next_action/due_date는 NULL 허용이며 백필하지 않는다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3a9c41b7d52"
down_revision: Union[str, Sequence[str], None] = "dd7f21f7190e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("deal_actions", "title", new_column_name="action")
    op.alter_column("deal_actions", "content", new_column_name="memo")
    op.add_column("deal_actions", sa.Column("next_action", sa.String(length=200), nullable=True))
    op.add_column("deal_actions", sa.Column("due_date", sa.Date(), nullable=True))
    op.create_index("ix_deal_actions_due_date", "deal_actions", ["due_date"], unique=False)
    # 소프트 삭제는 물리 삭제로 바뀌었으므로 삭제 표시된 활동 행만 정리한다(Deal 행은 유지).
    op.execute("DELETE FROM deal_actions WHERE deleted_at IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema. 정리된 소프트 삭제 행과 next_action/due_date 값은 복원되지 않는다."""
    op.drop_index("ix_deal_actions_due_date", table_name="deal_actions")
    op.drop_column("deal_actions", "due_date")
    op.drop_column("deal_actions", "next_action")
    op.alter_column("deal_actions", "memo", new_column_name="content")
    op.alter_column("deal_actions", "action", new_column_name="title")
