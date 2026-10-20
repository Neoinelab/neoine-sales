"""next_action_status: Next Action 상태와 Action 입력 분리

Revision ID: c7f1a9d3e5b2
Revises: b5e3a7c91d24
Create Date: 2026-10-20 10:00:00.000000

expand/contract 원칙의 예외(2026-10-15 결정, 사용자 승인 E3): 구 앱의 쓰기는 통과하지만
새 앱이 NULL 행을 만든 뒤 코드만 롤백하면 구 앱 읽기가 실패할 수 있다.
deal_actions의 action·next_action·due_date를 NULL 허용으로 바꾸고 next_action_status
(기존 행은 open)·next_action_closed_at을 추가한다. 데이터는 지우지 않는다.
downgrade는 NULL 값이 있는 행이 있으면 데이터를 지우지 않고 중단한다.
next_action_status의 server_default 'open'은 DB에만 둔다(ORM 모델에는 없음). 기존 행을 open으로
채우고, 상태 컬럼을 모르는 구 앱의 INSERT(항상 Next Action 있음)도 CHECK를 통과하게 하려는 것이다.
새 앱은 값을 항상 명시한다. 구 앱이 남지 않게 되면 contract 단계에서 이 기본값을 제거한다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7f1a9d3e5b2"
down_revision: Union[str, Sequence[str], None] = "b5e3a7c91d24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECKS = {
    "action_or_next": "action IS NOT NULL OR next_action IS NOT NULL",
    "next_action_fields": (
        "(next_action IS NULL) = (due_date IS NULL)"
        " AND (next_action IS NULL) = (next_action_status IS NULL)"
    ),
    "next_action_status": "next_action_status IN ('open', 'done', 'not_done')",
    "next_action_closed_at": (
        "(COALESCE(next_action_status, '') IN ('done', 'not_done'))"
        " = (next_action_closed_at IS NOT NULL)"
    ),
}


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "deal_actions",
        sa.Column(
            "next_action_status",
            sa.String(length=20),
            server_default=sa.text("'open'"),
            nullable=True,
        ),
    )
    op.add_column(
        "deal_actions",
        sa.Column("next_action_closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("deal_actions", "action", existing_type=sa.Text(), nullable=True)
    op.alter_column("deal_actions", "next_action", existing_type=sa.Text(), nullable=True)
    op.alter_column("deal_actions", "due_date", existing_type=sa.Date(), nullable=True)
    for name, condition in _CHECKS.items():
        op.create_check_constraint(name, "deal_actions", condition)


def downgrade() -> None:
    """Downgrade schema."""
    blocked = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM deal_actions"
                " WHERE action IS NULL OR next_action IS NULL OR due_date IS NULL"
            )
        )
        .scalar_one()
    )
    if blocked:
        raise RuntimeError(
            f"진행사항·Next Action·Due Date가 비어 있는 Action {blocked}건이 있어 "
            "downgrade를 중단합니다(데이터를 지우지 않습니다)."
        )
    for name in reversed(list(_CHECKS)):
        op.drop_constraint(op.f(f"ck_deal_actions_{name}"), "deal_actions", type_="check")
    op.alter_column("deal_actions", "due_date", existing_type=sa.Date(), nullable=False)
    op.alter_column("deal_actions", "next_action", existing_type=sa.Text(), nullable=False)
    op.alter_column("deal_actions", "action", existing_type=sa.Text(), nullable=False)
    op.drop_column("deal_actions", "next_action_closed_at")
    op.drop_column("deal_actions", "next_action_status")
