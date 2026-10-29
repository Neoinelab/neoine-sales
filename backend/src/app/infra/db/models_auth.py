"""사용자·로그인 실패·AD 설정 ORM 모델. models.py 끝에서 import해 같은 메타데이터에 등록한다."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.auth.principal import Role
from app.domain.directory.settings import SecurityMode
from app.domain.user.value_objects import UserDeleteReason
from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_ROLE_CODES = ", ".join(f"'{role.value}'" for role in Role)
_SECURITY_CODES = ", ".join(f"'{mode.value}'" for mode in SecurityMode)
_DELETE_REASON_CODES = ", ".join(f"'{reason.value}'" for reason in UserDeleteReason)


class UserRow(AuditColumns, Base):
    __tablename__ = "users"

    login_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    delete_reason: Mapped[str | None] = mapped_column(String(20), default=None)

    # login_id에는 유니크를 두지 않는다: 재직자 유일성은 응용 로직(roster 잠금)이 지킨다.
    __table_args__ = (
        CheckConstraint(f"role in ({_ROLE_CODES})", name="role_valid"),
        CheckConstraint(
            f"delete_reason is null or delete_reason in ({_DELETE_REASON_CODES})",
            name="delete_reason_valid",
        ),
        CheckConstraint("(deleted_at is null) = (delete_reason is null)", name="deleted_pair"),
        Index("ix_users_login_id_lower", func.lower(login_id)),
        Index("ix_users_created_at_id", "created_at", "id"),
        Index("ix_users_created_by_user_id", "created_by_user_id"),
    )


class LoginFailureRow(Base):
    __tablename__ = "login_failures"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (CheckConstraint("failures >= 0", name="failures_non_negative"),)


class DirectorySettingsRow(Base):
    """AD 접속 설정(서비스 계정). id=1 단일 행이며 revision으로 낙관적 잠금을 한다.

    바인드 비밀번호는 평문이 아니라 SecretCipher가 만든 토큰(bind_password_encrypted)으로 저장한다.
    """

    __tablename__ = "directory_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(Integer)
    host: Mapped[str] = mapped_column(String(253))
    port: Mapped[int] = mapped_column(Integer)
    security: Mapped[str] = mapped_column(String(16))
    bind_account: Mapped[str] = mapped_column(String(256))
    bind_password_encrypted: Mapped[str] = mapped_column(Text)
    base_dn: Mapped[str] = mapped_column(String(512))
    user_filter: Mapped[str] = mapped_column(String(512))
    connect_timeout_seconds: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        Index("ix_directory_settings_updated_by_user_id", "updated_by_user_id"),
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("connect_timeout_seconds between 1 and 30", name="connect_timeout_range"),
        CheckConstraint("port between 1 and 65535", name="port_range"),
        CheckConstraint(f"security in ({_SECURITY_CODES})", name="security_values"),
    )


class UserPasswordHashRow(Base):
    """AD 장애 때 쓰는 대체 로그인용 비밀번호 해시. 사용자당 한 행, 사용자 삭제 때 함께 지운다."""

    __tablename__ = "user_password_hashes"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    password_hash: Mapped[str] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
