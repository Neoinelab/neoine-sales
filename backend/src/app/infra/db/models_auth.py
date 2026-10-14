"""사용자·로그인 실패·AD 설정 ORM 모델. models.py 끝에서 import해 같은 메타데이터에 등록한다."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.auth.principal import Role
from app.domain.user.value_objects import UserDeleteReason
from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_ROLE_CODES = ", ".join(f"'{role.value}'" for role in Role)
_DELETE_REASON_CODES = ", ".join(f"'{reason.value}'" for reason in UserDeleteReason)


class UserRow(AuditColumns, Base):
    __tablename__ = "users"

    login_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
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
    """AD 접속 설정. id=1 단일 행이며 revision으로 낙관적 잠금을 한다."""

    __tablename__ = "directory_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(Integer)
    server_urls: Mapped[list[Any]] = mapped_column(JSONB)
    use_starttls: Mapped[bool] = mapped_column(Boolean)
    ca_cert_pem: Mapped[str | None] = mapped_column(Text, default=None)
    bind_template: Mapped[str] = mapped_column(String(256))
    base_dn: Mapped[str] = mapped_column(String(512))
    user_filter: Mapped[str] = mapped_column(String(512))
    display_name_attribute: Mapped[str] = mapped_column(String(64))
    email_attribute: Mapped[str] = mapped_column(String(64))
    connect_timeout_seconds: Mapped[int] = mapped_column(SmallInteger)
    receive_timeout_seconds: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        Index("ix_directory_settings_updated_by_user_id", "updated_by_user_id"),
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("connect_timeout_seconds between 1 and 30", name="connect_timeout_range"),
        CheckConstraint("receive_timeout_seconds between 1 and 60", name="receive_timeout_range"),
    )
