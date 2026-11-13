"""users 등록자(created_by_user_id)·퇴사 사유(delete_reason) 제거

Revision ID: c8e3f1a7d295
Revises: b4d7e2a9c613
Create Date: 2026-11-13 00:00:00.000000

upgrade는 CHECK 2개·FK·인덱스를 지우고 컬럼 2개를 drop한다. 행과 deleted_at은 그대로 둔다
(등록자·사유 값만 버림, 2026-11-13 사용자 승인 contract). 퇴사 여부는 deleted_at으로 판정한다.
downgrade는 등록자를 각 행 자기 id로, 퇴사 행의 사유를 'resigned'로 채워 되살린다(원래 값은 복구되지 않는다).
product 적용은 배포 전 pg_dump 후 사람 승인. 코드만 롤백하면 구 앱이 실패하므로 downgrade를 함께 한다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e3f1a7d295"
down_revision: Union[str, Sequence[str], None] = "b4d7e2a9c613"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("deleted_pair", "users", type_="check")
    op.drop_constraint("delete_reason_valid", "users", type_="check")
    op.drop_index("ix_users_created_by_user_id", table_name="users")
    op.drop_constraint("fk_users_created_by_user_id_users", "users", type_="foreignkey")
    op.drop_column("users", "created_by_user_id")
    op.drop_column("users", "delete_reason")


def downgrade() -> None:
    op.add_column("users", sa.Column("created_by_user_id", sa.BigInteger(), nullable=True))
    op.execute("UPDATE users SET created_by_user_id = id")
    op.alter_column("users", "created_by_user_id", nullable=False)
    op.create_foreign_key(
        "fk_users_created_by_user_id_users",
        "users",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_users_created_by_user_id", "users", ["created_by_user_id"])
    op.add_column("users", sa.Column("delete_reason", sa.String(length=20), nullable=True))
    op.execute("UPDATE users SET delete_reason = 'resigned' WHERE deleted_at IS NOT NULL")
    op.create_check_constraint(
        "delete_reason_valid",
        "users",
        "delete_reason IS NULL OR delete_reason IN ('resigned')",
    )
    op.create_check_constraint(
        "deleted_pair", "users", "(deleted_at IS NULL) = (delete_reason IS NULL)"
    )
