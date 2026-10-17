"""경고 기준 설정 ORM 모델. models.py 끝에서 import해 등록한다."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class AlertSettingsRow(Base):
    """Deal 미업데이트 경고 기준. id=1 단일 행(시드 없음, 저장 전에는 기본값)."""

    __tablename__ = "alert_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    stale_days: Mapped[int] = mapped_column(SmallInteger)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))

    __table_args__ = (
        CheckConstraint("id = 1", name="single_row"),
        CheckConstraint("stale_days BETWEEN 1 AND 365", name="stale_days_range"),
        Index("ix_alert_settings_updated_by_user_id", "updated_by_user_id"),
    )
