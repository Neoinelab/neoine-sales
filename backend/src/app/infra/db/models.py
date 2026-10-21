"""ORM 모델. 도메인 엔티티와 분리되어 있으며 변환은 각 Repository가 맡는다.

Deal 원장(deals와 딸린 테이블)은 models_deal.py, 연락처·코드·Label·사용자는 각 models_*.py에 있다.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, identity_key


class AuditColumns:
    """모든 테이블 공통: 식별자, 생성·수정 시각."""

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DealActionRow(AuditColumns, Base):
    """Deal 진행 활동. Deal을 지우면 함께 지워진다(CASCADE)."""

    __tablename__ = "deal_actions"

    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    action_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("action_types.id", ondelete="RESTRICT")
    )
    action: Mapped[str | None] = mapped_column(Text, default=None)
    next_action: Mapped[str | None] = mapped_column(Text, default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    memo: Mapped[str] = mapped_column(Text, default="")
    # Next Action이 있는 행에만 상태가 있다(없으면 NULL). 종료 상태일 때만 종료 시각이 있다.
    # 서버 기본값은 없다(앱이 항상 값을 정한다). 구 앱 호환용 'open' 기본값은 bigint_ids에서 뺐다.
    next_action_status: Mapped[str | None] = mapped_column(String(20), default=None)
    next_action_closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
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
        CheckConstraint("action IS NOT NULL OR next_action IS NOT NULL", name="action_or_next"),
        CheckConstraint(
            "(next_action IS NULL) = (due_date IS NULL)"
            " AND (next_action IS NULL) = (next_action_status IS NULL)",
            name="next_action_fields",
        ),
        CheckConstraint(
            "next_action_status IN ('open', 'done', 'not_done')", name="next_action_status"
        ),
        CheckConstraint(
            "(COALESCE(next_action_status, '') IN ('done', 'not_done'))"
            " = (next_action_closed_at IS NOT NULL)",
            name="next_action_closed_at",
        ),
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
        Index("ix_deal_actions_deal_id_acted_at", "deal_id", "acted_at"),
        Index("ix_deal_actions_acted_at", "acted_at"),
        Index("ix_deal_actions_due_date", "due_date"),
    )


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="RESTRICT"))
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
