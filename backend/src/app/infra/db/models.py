"""ORM 모델. 도메인 엔티티와 분리되어 있으며 변환은 각 Repository가 맡는다."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.deal.stage import DealStage
from app.infra.db.base import Base

_STAGE_CODES = ", ".join(f"'{stage.value}'" for stage in DealStage)


class AuditColumns:
    """모든 테이블 공통: 식별자, 생성·수정 시각, 소프트 삭제 표시."""

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class CustomerRow(AuditColumns, Base):
    __tablename__ = "customers"

    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_title: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)
    employee_count: Mapped[int | None] = mapped_column(Integer, default=None)
    notes: Mapped[str] = mapped_column(String(2000), default="")

    __table_args__ = (
        CheckConstraint(
            "employee_count is null or employee_count >= 0", name="employee_count_non_negative"
        ),
        Index("ix_customers_created_at_id", "created_at", "id"),
    )


class PartnerRow(AuditColumns, Base):
    __tablename__ = "partners"

    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(100))
    contact_title: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)

    __table_args__ = (Index("ix_partners_created_at_id", "created_at", "id"),)


class DealRow(AuditColumns, Base):
    __tablename__ = "deals"

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(100))
    vendor: Mapped[str] = mapped_column(String(100))
    solution: Mapped[str] = mapped_column(String(200))
    revenue_amount: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    revenue_currency: Mapped[str] = mapped_column(String(3))
    revenue_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[UUID] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    partner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("partners.id", ondelete="RESTRICT"), default=None
    )
    stage: Mapped[str] = mapped_column(
        String(30), default=DealStage.PROSPECTING.value, server_default=DealStage.PROSPECTING.value
    )
    owner_user_id: Mapped[str | None] = mapped_column(String(200), default=None)

    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint("revenue_amount >= 0", name="revenue_non_negative"),
        CheckConstraint(f"stage in ({_STAGE_CODES})", name="stage_valid"),
        Index("ix_deals_created_at_id", "created_at", "id"),
        Index("ix_deals_customer_id", "customer_id"),
        Index("ix_deals_partner_id", "partner_id"),
        Index("ix_deals_owner_user_id", "owner_user_id"),
    )


class DealActionRow(AuditColumns, Base):
    __tablename__ = "deal_actions"

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"))
    action_type: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(200))
    next_action: Mapped[str | None] = mapped_column(String(200), default=None)
    due_date: Mapped[date | None] = mapped_column(Date, default=None)
    memo: Mapped[str] = mapped_column(String(4000), default="")
    acted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor: Mapped[str] = mapped_column(String(100))

    __table_args__ = (
        Index("ix_deal_actions_deal_id_acted_at", "deal_id", "acted_at"),
        Index("ix_deal_actions_acted_at", "acted_at"),
        Index("ix_deal_actions_due_date", "due_date"),
    )


class DealStageChangeRow(Base):
    """불변 단계 변경 이력. 수정·삭제가 없어 AuditColumns를 쓰지 않는다."""

    __tablename__ = "deal_stage_changes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="RESTRICT"))
    from_stage: Mapped[str] = mapped_column(String(30))
    to_stage: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(String(500), default=None)
    changed_by_subject: Mapped[str] = mapped_column(String(200))
    changed_by_name: Mapped[str] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"from_stage in ({_STAGE_CODES})", name="from_stage_valid"),
        CheckConstraint(f"to_stage in ({_STAGE_CODES})", name="to_stage_valid"),
        Index("ix_deal_stage_changes_deal_id_changed_at", "deal_id", "changed_at"),
    )


class AuthSessionRow(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        UniqueConstraint("token_hash"),
        Index("ix_auth_sessions_expires_at", "expires_at"),
        Index("ix_auth_sessions_subject", "subject"),
    )


# 새 모델을 Base.metadata에 등록한다(alembic env.py는 이 모듈만 import한다).
from app.infra.db import models_auth  # noqa: E402,F401
