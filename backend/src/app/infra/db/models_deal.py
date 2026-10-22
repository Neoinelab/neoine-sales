"""Deal 원장 ORM 모델: deals와 딸린 테이블(파트너 링크, BANT 선택, 이력).

models.py 끝에서 import해 등록한다. Deal의 PK는 infra 전용 대리 키 `id`이고, 업무 키인
deal_code(`YYYYMMDD-XXXX`)는 UNIQUE다. 딸린 테이블은 `deal_id`로 참조하며 Deal을 지우면
함께 지워진다(CASCADE).
"""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.bant.values import BantCategory
from app.domain.code.values import CodeKind
from app.domain.deal.history import HistoryCategory
from app.domain.deal.values import AMOUNT_MAX, PocState, QuoteSubmitted
from app.infra.db.base import Base, identity_key

if TYPE_CHECKING:
    from collections.abc import Iterable
    from enum import StrEnum

DEAL_CODE_LENGTH = 13


def _in_list(values: Iterable[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in values)


class DealRow(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    deal_code: Mapped[str] = mapped_column(String(DEAL_CODE_LENGTH))
    name: Mapped[str] = mapped_column(String(200))
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    vendor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("vendors.id", ondelete="RESTRICT"), default=None
    )
    solution: Mapped[str] = mapped_column(String(200))
    users: Mapped[int] = mapped_column(Integer)
    status_kind: Mapped[str] = mapped_column(String(20), default=CodeKind.STATUS.value)
    status_key: Mapped[str] = mapped_column(String(50))
    forecast_kind: Mapped[str] = mapped_column(String(20), default=CodeKind.FORECAST.value)
    forecast_key: Mapped[str] = mapped_column(String(50))
    revenue_amount: Mapped[int] = mapped_column(BigInteger)
    revenue_date: Mapped[date] = mapped_column(Date)
    customer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contacts.id", ondelete="RESTRICT")
    )
    quote_submitted: Mapped[str | None] = mapped_column(String(3), default=None)
    quote_submitted_date: Mapped[date | None] = mapped_column(Date, default=None)
    poc_state: Mapped[str | None] = mapped_column(String(3), default=None)
    poc_completed_date: Mapped[date | None] = mapped_column(Date, default=None)
    procurement: Mapped[str] = mapped_column(String(500), default="")
    status_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("deal_code"),
        CheckConstraint("deal_code ~ '^[0-9]{8}-[A-Z0-9]{4}$'", name="code_format"),
        CheckConstraint("users >= 0", name="users_positive"),
        CheckConstraint(f"status_kind = '{CodeKind.STATUS.value}'", name="status_kind"),
        CheckConstraint(f"forecast_kind = '{CodeKind.FORECAST.value}'", name="forecast_kind"),
        CheckConstraint(f"revenue_amount between 1 and {AMOUNT_MAX}", name="amount_range"),
        CheckConstraint(
            "(status_key = 'contract_completed') = (forecast_key = 'won')", name="won_sync"
        ),
        CheckConstraint(
            f"quote_submitted is null or quote_submitted in ({_in_list(QuoteSubmitted)})",
            name="quote_valid",
        ),
        CheckConstraint(
            f"poc_state is null or poc_state in ({_in_list(PocState)})", name="poc_valid"
        ),
        ForeignKeyConstraint(
            ["status_kind", "status_key"],
            ["codes.kind", "codes.key"],
            name="fk_deals_status_code",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["forecast_kind", "forecast_key"],
            ["codes.kind", "codes.key"],
            name="fk_deals_forecast_code",
            ondelete="RESTRICT",
        ),
        Index("ix_deals_owner_user_id", "owner_user_id"),
        Index("ix_deals_vendor_id", "vendor_id"),
        Index("ix_deals_status_key", "status_key"),
        Index("ix_deals_forecast_key", "forecast_key"),
        Index("ix_deals_revenue_date", "revenue_date"),
        Index("ix_deals_updated_at", "updated_at"),
        Index("ix_deals_customer_id", "customer_id"),
    )


class DealPartnerRow(Base):
    """Deal과 파트너 연락처의 연결 이력. 활성 링크(해제 시각 없음)는 Deal당 최대 1건이다."""

    __tablename__ = "deal_partners"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("contacts.id", ondelete="RESTRICT")
    )
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        CheckConstraint("unlinked_at is null or unlinked_at >= linked_at", name="period"),
        Index(
            "uq_deal_partners_one_active",
            "deal_id",
            unique=True,
            postgresql_where=text("unlinked_at is null"),
        ),
        Index("ix_deal_partners_contact_id", "contact_id"),
        Index("ix_deal_partners_deal_id_linked_at", "deal_id", "linked_at"),
    )


class DealBantLabelRow(Base):
    """Deal의 BANT 선택. 구분당 하나이고 복합 FK(label_id, category)로 구분이 맞는 Label만 허용."""

    __tablename__ = "deal_bant_labels"

    deal_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("deals.id", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(String(20), primary_key=True)
    label_id: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        CheckConstraint(f"category in ({_in_list(BantCategory)})", name="category_valid"),
        ForeignKeyConstraint(
            ["label_id", "category"],
            ["bant_labels.id", "bant_labels.category"],
            name="fk_deal_bant_labels_label",
            ondelete="RESTRICT",
        ),
        Index("ix_deal_bant_labels_label_id", "label_id"),
    )


class DealHistoryRow(Base):
    """불변 변경 이력. 수정이 없어 AuditColumns를 쓰지 않고 id는 DB가 늘려 준다."""

    __tablename__ = "deal_history"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    category: Mapped[str] = mapped_column(String(20))
    target: Mapped[str] = mapped_column(String(300))
    before_text: Mapped[str] = mapped_column(Text)
    after_text: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"category in ({_in_list(HistoryCategory)})", name="category"),
        Index("ix_deal_history_deal_id_changed_at", "deal_id", "changed_at"),
        Index("ix_deal_history_changed_by_user_id", "changed_by_user_id"),
    )
