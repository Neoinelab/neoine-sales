"""ORM 모델. 도메인 엔티티와 분리되어 있으며 변환은 각 Repository가 맡는다.

Deal 원장(deals와 딸린 테이블)은 models_deal.py, 연락처·코드·Label·사용자는 각 models_*.py에 있다.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base


class AuditColumns:
    """모든 테이블 공통: 식별자, 생성·수정 시각."""

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DealActionRow(AuditColumns, Base):
    """Deal 진행 활동. Deal을 지우면 함께 지워진다(CASCADE)."""

    __tablename__ = "deal_actions"

    deal_code: Mapped[str] = mapped_column(
        String(13), ForeignKey("deals.deal_code", ondelete="CASCADE")
    )
    action_type_id: Mapped[UUID] = mapped_column(ForeignKey("action_types.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(Text)
    next_action: Mapped[str] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    memo: Mapped[str] = mapped_column(Text, default="")
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # 기록 시점의 Status·Forecast 스냅숏. 이후 Deal이 바뀌어도 따라가지 않는다.
    status_kind: Mapped[str] = mapped_column(
        String(20), default="status", server_default=text("'status'")
    )
    status_key: Mapped[str] = mapped_column(String(50))
    forecast_kind: Mapped[str] = mapped_column(
        String(20), default="forecast", server_default=text("'forecast'")
    )
    forecast_key: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        CheckConstraint("status_kind = 'status'", name="status_kind"),
        CheckConstraint("forecast_kind = 'forecast'", name="forecast_kind"),
        ForeignKeyConstraint(
            ["status_kind", "status_key"],
            ["codes.kind", "codes.key"],
            name="fk_deal_actions_status_code",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["forecast_kind", "forecast_key"],
            ["codes.kind", "codes.key"],
            name="fk_deal_actions_forecast_code",
            ondelete="RESTRICT",
        ),
        Index("ix_deal_actions_action_type_id", "action_type_id"),
        Index("ix_deal_actions_status_key", "status_key"),
        Index("ix_deal_actions_forecast_key", "forecast_key"),
        Index("ix_deal_actions_actor_user_id", "actor_user_id"),
        Index("ix_deal_actions_deal_code_acted_at", "deal_code", "acted_at"),
        Index("ix_deal_actions_acted_at", "acted_at"),
        Index("ix_deal_actions_due_date", "due_date"),
    )


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        UniqueConstraint("token_hash"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
        Index("ix_auth_sessions_user_id", "user_id"),
    )


# 새 모델을 Base.metadata에 등록한다(alembic env.py는 이 모듈만 import한다).
from app.infra.db import (  # noqa: E402,F401
    models_alert,
    models_attachment,
    models_auth,
    models_catalog,
    models_contact,
    models_deal,
)
