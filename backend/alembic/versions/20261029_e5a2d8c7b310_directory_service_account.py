"""directory_service_account: AD 설정을 서비스 계정 방식으로 바꾸고 대체 로그인 해시 테이블 추가

Revision ID: e5a2d8c7b310
Revises: c4e8a1d7f203
Create Date: 2026-10-29 10:00:00.000000

expand/contract 원칙의 예외(사용자 승인, 앱과 같은 배포 전제, product에는 사용자·설정이 아직 없다):
- directory_settings의 기존 행을 지운다. 옛 설정(서버 URL 목록·사용자 바인드 템플릿·CA 인증서)은
  새 방식(호스트·포트·보안 연결·서비스 계정 + 암호화된 비밀번호)으로 변환할 수 없고, 서비스 계정
  비밀번호가 없으므로 다시 입력해야 한다. 지운 뒤에는 최초 설정 화면에서 다시 등록한다.
- 옛 컬럼 7개를 삭제하고 새 컬럼 5개와 CHECK 제약(port_range, security_values)을 추가한다.
  receive_timeout_range 제약은 컬럼과 함께 사라진다.
- user_password_hashes를 만든다(AD 장애 때의 대체 로그인용 scrypt 해시, 사용자 삭제 때 CASCADE).
구 앱은 새 스키마에서 AD 설정을 읽지 못하고, 코드만 롤백하면 구 앱이 지워진 컬럼을 읽다 실패하므로
`downgrade -1`이 필수다. downgrade는 설정 행을 지우고 옛 컬럼을 되살리며 해시 테이블을 지운다(해시 소실).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e5a2d8c7b310"
down_revision: Union[str, Sequence[str], None] = "c4e8a1d7f203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_COLUMNS = (
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "display_name_attribute",
    "email_attribute",
    "receive_timeout_seconds",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DELETE FROM directory_settings")
    op.drop_constraint("ck_directory_settings_receive_timeout_range", "directory_settings")
    for column in OLD_COLUMNS:
        op.drop_column("directory_settings", column)
    op.add_column("directory_settings", sa.Column("host", sa.String(length=253), nullable=False))
    op.add_column("directory_settings", sa.Column("port", sa.Integer(), nullable=False))
    op.add_column("directory_settings", sa.Column("security", sa.String(length=16), nullable=False))
    op.add_column(
        "directory_settings", sa.Column("bind_account", sa.String(length=256), nullable=False)
    )
    op.add_column(
        "directory_settings", sa.Column("bind_password_encrypted", sa.Text(), nullable=False)
    )
    op.create_check_constraint(
        op.f("ck_directory_settings_port_range"), "directory_settings", "port between 1 and 65535"
    )
    op.create_check_constraint(
        op.f("ck_directory_settings_security_values"),
        "directory_settings",
        "security in ('none', 'ssl', 'starttls')",
    )
    op.create_table(
        "user_password_hashes",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_password_hashes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_password_hashes")),
    )


def downgrade() -> None:
    """Downgrade schema. 설정 행과 해시는 되살릴 수 없다."""
    op.drop_table("user_password_hashes")
    op.execute("DELETE FROM directory_settings")
    op.drop_constraint("ck_directory_settings_security_values", "directory_settings")
    op.drop_constraint("ck_directory_settings_port_range", "directory_settings")
    for column in ("bind_password_encrypted", "bind_account", "security", "port", "host"):
        op.drop_column("directory_settings", column)
    op.add_column(
        "directory_settings",
        sa.Column("server_urls", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.add_column("directory_settings", sa.Column("use_starttls", sa.Boolean(), nullable=False))
    op.add_column("directory_settings", sa.Column("ca_cert_pem", sa.Text(), nullable=True))
    op.add_column(
        "directory_settings", sa.Column("bind_template", sa.String(length=256), nullable=False)
    )
    op.add_column(
        "directory_settings",
        sa.Column("display_name_attribute", sa.String(length=64), nullable=False),
    )
    op.add_column(
        "directory_settings", sa.Column("email_attribute", sa.String(length=64), nullable=False)
    )
    op.add_column(
        "directory_settings",
        sa.Column("receive_timeout_seconds", sa.SmallInteger(), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_directory_settings_receive_timeout_range"),
        "directory_settings",
        "receive_timeout_seconds between 1 and 60",
    )
