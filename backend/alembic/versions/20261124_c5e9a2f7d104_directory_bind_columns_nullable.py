"""AD 바인드 컬럼 NULL 허용: directory_settings.bind_account·bind_password_encrypted

Revision ID: c5e9a2f7d104
Revises: c9f2a6b8d401
Create Date: 2026-11-24 10:00:00.000000

AD 서비스 계정 폐지(2026-11-24)로 새 앱은 두 컬럼을 쓰지 않는다. NOT NULL 제약만 풀고 기존 행·값은
그대로 둔다(순수 expand, DELETE·UPDATE·drop 없음). 컬럼 제거(contract)는 사람 승인 뒤 별도 리비전.
downgrade는 두 컬럼 중 하나라도 NULL인 행이 있으면 건수와 함께 중단한다(행 삭제·값 채우기 없음).
코드만 롤백하면 새 앱이 만든 행(두 값 NULL)을 구 앱이 읽지 못하므로 forward fix를 우선한다.
product 적용은 배포 전 pg_dump 후 사람 승인.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5e9a2f7d104"
down_revision: Union[str, Sequence[str], None] = "c9f2a6b8d401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "directory_settings", "bind_account", existing_type=sa.String(length=256), nullable=True
    )
    op.alter_column(
        "directory_settings", "bind_password_encrypted", existing_type=sa.Text(), nullable=True
    )


def downgrade() -> None:
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "select count(*) from directory_settings"
                " where bind_account is null or bind_password_encrypted is null"
            )
        )
        .scalar_one()
    )
    if rows:
        raise RuntimeError(
            f"directory_settings에 바인드 계정이 비어 있는 행 {rows}건이 있어 "
            "downgrade할 수 없습니다(행은 삭제하지 않음)."
        )
    op.alter_column(
        "directory_settings", "bind_password_encrypted", existing_type=sa.Text(), nullable=False
    )
    op.alter_column(
        "directory_settings", "bind_account", existing_type=sa.String(length=256), nullable=False
    )
