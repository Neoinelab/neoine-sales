"""auth_mode_and_user_phone: 인증 방식(auth_settings)과 users.phone 추가

Revision ID: af477447ba9f
Revises: e5a2d8c7b310
Create Date: 2026-11-02 16:08:35.448306

순수 expand(하위 호환): 새 테이블과 NULL 허용 컬럼만 추가하므로 구 앱은 둘 다 읽지 않는다.
재직 admin이나 AD 설정(directory_settings)이 있는 기존 시스템은 mode='ad'로 채운다.
둘 다 없으면 행을 만들지 않는다(최초 설정에서 고른다).
downgrade는 users.phone(전화번호 소실)과 auth_settings를 지운다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "af477447ba9f"
down_revision: Union[str, Sequence[str], None] = "e5a2d8c7b310"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "auth_settings",
        sa.Column("id", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("mode in ('ad', 'local')", name=op.f("ck_auth_settings_mode_valid")),
        sa.CheckConstraint("id = 1", name=op.f("ck_auth_settings_single_row")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_settings")),
    )
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))
    op.execute(
        "insert into auth_settings (id, mode, updated_at) "
        "select 1, 'ad', now() where "
        "exists (select 1 from users where role = 'admin' and deleted_at is null) "
        "or exists (select 1 from directory_settings)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "phone")
    op.drop_table("auth_settings")
