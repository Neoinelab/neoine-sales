"""action_snapshot: Action의 Status·Forecast 스냅숏과 무제한 텍스트 (P2 M-P2)

Revision ID: 9c3f5a7d2e18
Revises: 7b2e4c9a1d35
Create Date: 2026-10-16 18:00:00.000000

보존 데이터 없음 전제(사용자 결정 2026-10-15): deal_actions의 행을 모두 지운다(Deal은 남는다).
expand/contract 원칙의 예외이며 구 앱은 이 스키마와 호환되지 않으므로 앱과 같이 배포한다.

변경: status_kind/status_key/forecast_kind/forecast_key(NOT NULL, kind 기본값, 체크, codes 복합 FK
RESTRICT, key 선두 인덱스), next_action·due_date NOT NULL, action·next_action·memo를 TEXT로.

downgrade: 행을 먼저 지운 뒤 이전 리비전의 구조(VARCHAR, next_action·due_date NULL 허용)로 되돌린다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3f5a7d2e18"
down_revision: Union[str, Sequence[str], None] = "7b2e4c9a1d35"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SNAPSHOTS = (
    ("status", "ck_deal_actions_status_kind"),
    ("forecast", "ck_deal_actions_forecast_kind"),
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM deal_actions")
    for kind, check in _SNAPSHOTS:
        op.add_column(
            "deal_actions",
            sa.Column(
                f"{kind}_kind",
                sa.String(length=20),
                server_default=sa.text(f"'{kind}'"),
                nullable=False,
            ),
        )
        op.add_column(
            "deal_actions", sa.Column(f"{kind}_key", sa.String(length=50), nullable=False)
        )
        op.create_check_constraint(op.f(check), "deal_actions", f"{kind}_kind = '{kind}'")
        op.create_foreign_key(
            f"fk_deal_actions_{kind}_code",
            "deal_actions",
            "codes",
            [f"{kind}_kind", f"{kind}_key"],
            ["kind", "key"],
            ondelete="RESTRICT",
        )
        op.create_index(f"ix_deal_actions_{kind}_key", "deal_actions", [f"{kind}_key"])
    for column in ("action", "next_action", "memo"):
        op.alter_column("deal_actions", column, type_=sa.Text(), nullable=False)
    op.alter_column("deal_actions", "due_date", existing_type=sa.Date(), nullable=False)


def downgrade() -> None:
    """Downgrade schema (행은 복원하지 않는다)."""
    op.execute("DELETE FROM deal_actions")
    op.alter_column("deal_actions", "due_date", existing_type=sa.Date(), nullable=True)
    op.alter_column("deal_actions", "action", type_=sa.String(length=200), nullable=False)
    op.alter_column("deal_actions", "next_action", type_=sa.String(length=200), nullable=True)
    op.alter_column("deal_actions", "memo", type_=sa.String(length=4000), nullable=False)
    for kind, check in reversed(_SNAPSHOTS):
        op.drop_index(f"ix_deal_actions_{kind}_key", table_name="deal_actions")
        op.drop_constraint(f"fk_deal_actions_{kind}_code", "deal_actions", type_="foreignkey")
        op.drop_constraint(op.f(check), "deal_actions", type_="check")
        op.drop_column("deal_actions", f"{kind}_key")
        op.drop_column("deal_actions", f"{kind}_kind")
