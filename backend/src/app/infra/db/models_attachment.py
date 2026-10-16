"""파일 저장 위치 설정과 Deal 첨부 ORM 모델. models.py 끝에서 import해 등록한다."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_MAX_FILE_BYTES = (
    104857600  # domain.attachment.values.MAX_FILE_BYTES와 같다(마이그레이션에 고정된 값)
)


class StorageSettingsRow(Base):
    """파일 저장 위치. id=1 단일 행."""

    __tablename__ = "storage_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    path: Mapped[str] = mapped_column(String(1024))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        Index("ix_storage_settings_updated_by_user_id", "updated_by_user_id"),
    )


class DealAttachmentRow(AuditColumns, Base):
    """Deal 첨부 파일 메타데이터. Deal을 지우면 함께 지워진다(CASCADE). 본문은 디스크에 있다."""

    __tablename__ = "deal_attachments"

    deal_code: Mapped[str] = mapped_column(
        String(13), ForeignKey("deals.deal_code", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(100), default="", server_default=text("''"))
    mime: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(32))
    uploaded_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"size_bytes between 0 and {_MAX_FILE_BYTES}", name="size_range"),
        UniqueConstraint("deal_code", "file_name", name="uq_deal_attachments_deal_code_file_name"),
        UniqueConstraint("storage_key"),
        Index("ix_deal_attachments_uploaded_by_user_id", "uploaded_by_user_id"),
        Index("ix_deal_attachments_deal_code_uploaded_at", "deal_code", "uploaded_at"),
    )
