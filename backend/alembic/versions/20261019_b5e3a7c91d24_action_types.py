"""action_types: Action 유형 카탈로그

Revision ID: b5e3a7c91d24
Revises: 7a185add9ec4
Create Date: 2026-10-19 15:00:00.000000

expand/contract 원칙의 예외(사용자 승인, 보존 데이터 없음, 앱과 같은 배포 전제):
action_types를 만들고 기본 유형 8개를 시드한 뒤 deal_actions 행을 모두 지우고
deal_actions.action_type(문자열)을 action_type_id(NOT NULL, FK RESTRICT)로 교체한다.
deal_history 행은 deal_actions와 FK가 없어 그대로 남는다.
downgrade는 action_type 컬럼을 되살리고 action_types를 지운다(그 시점의 Action 행도 지운다).
"""

from datetime import datetime, UTC
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b5e3a7c91d24"
down_revision: Union[str, Sequence[str], None] = "7a185add9ec4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 기본 유형(순서 1~8). tests/fakes/catalog_seed.py의 기본 유형과 같아야 한다.
_DEFAULT_TYPES = ("통화", "미팅", "이메일", "데모", "제안", "협상", "계약", "기타")


def upgrade() -> None:
    """Upgrade schema."""
    action_types = op.create_table(
        "action_types",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("default_order", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "is_default = (default_order is not null)", name=op.f("ck_action_types_default_order")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_action_types_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_action_types")),
    )
    op.create_index(
        "uq_action_types_name_lower",
        "action_types",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.create_index(
        "ix_action_types_created_by_user_id", "action_types", ["created_by_user_id"], unique=False
    )
    now = datetime.now(UTC)
    op.bulk_insert(
        action_types,
        [
            {
                "id": uuid4(),
                "name": name,
                "is_default": True,
                "default_order": order,
                "created_by_user_id": None,
                "created_at": now,
                "updated_at": now,
            }
            for order, name in enumerate(_DEFAULT_TYPES, start=1)
        ],
    )
    op.execute("DELETE FROM deal_actions")
    op.drop_column("deal_actions", "action_type")
    op.add_column("deal_actions", sa.Column("action_type_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        op.f("fk_deal_actions_action_type_id_action_types"),
        "deal_actions",
        "action_types",
        ["action_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_deal_actions_action_type_id", "deal_actions", ["action_type_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema. 그 시점의 Action 행은 지운다."""
    op.execute("DELETE FROM deal_actions")
    op.drop_index("ix_deal_actions_action_type_id", table_name="deal_actions")
    op.drop_constraint(
        op.f("fk_deal_actions_action_type_id_action_types"), "deal_actions", type_="foreignkey"
    )
    op.drop_column("deal_actions", "action_type_id")
    op.add_column("deal_actions", sa.Column("action_type", sa.String(length=20), nullable=False))
    op.drop_index("ix_action_types_created_by_user_id", table_name="action_types")
    op.drop_index("uq_action_types_name_lower", table_name="action_types")
    op.drop_table("action_types")
