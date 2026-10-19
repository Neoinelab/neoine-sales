"""코드(Status·Forecast)와 BANT Label ORM 모델. models.py 끝에서 import해 등록한다."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.bant.values import BantCategory
from app.domain.code.values import CodeKind, ForecastOutcome
from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

if TYPE_CHECKING:
    from collections.abc import Iterable
    from enum import StrEnum


def _in_list(enum: Iterable[StrEnum]) -> str:
    return ", ".join(f"'{member.value}'" for member in enum)


class CodeRow(AuditColumns, Base):
    """Status·Forecast 코드. 같은 종류 안에서 key와 이름(대소문자 무시)이 고유하다."""

    __tablename__ = "codes"

    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(10), default=ForecastOutcome.OPEN.value)
    probability_hint: Mapped[str | None] = mapped_column(String(20), default=None)

    __table_args__ = (
        CheckConstraint(f"kind in ({_in_list(CodeKind)})", name="kind_valid"),
        CheckConstraint("key ~ '^[a-z][a-z0-9_]{0,49}$'", name="key_format"),
        CheckConstraint("sort_order >= 1", name="order_positive"),
        CheckConstraint(f"outcome in ({_in_list(ForecastOutcome)})", name="outcome_valid"),
        CheckConstraint(
            f"kind <> '{CodeKind.STATUS.value}' or outcome = '{ForecastOutcome.OPEN.value}'",
            name="status_outcome_open",
        ),
        CheckConstraint(
            f"kind <> '{CodeKind.STATUS.value}' or probability_hint is null",
            name="hint_forecast_only",
        ),
        # Deal의 복합 FK가 가리키려면 인덱스가 아니라 제약이어야 한다.
        UniqueConstraint("kind", "key", name="uq_codes_kind_key"),
        Index("uq_codes_kind_name_lower", "kind", func.lower(name), unique=True),
        Index("ix_codes_kind_sort_order", "kind", "sort_order"),
    )


class BantLabelRow(AuditColumns, Base):
    """BANT Label. 기본 Label(시드)은 생성자가 없고 default_order를 가진다."""

    __tablename__ = "bant_labels"

    category: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    default_order: Mapped[int | None] = mapped_column(Integer, default=None)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        CheckConstraint(f"category in ({_in_list(BantCategory)})", name="category_valid"),
        CheckConstraint("is_default = (default_order is not null)", name="default_order"),
        # Deal의 BANT 선택이 (label_id, category) 복합 FK로 구분이 맞는 Label만 가리키게 한다.
        UniqueConstraint("id", "category", name="uq_bant_labels_id_category"),
        Index("uq_bant_labels_category_name_lower", "category", func.lower(name), unique=True),
        Index("ix_bant_labels_created_by_user_id", "created_by_user_id"),
    )


class ActionTypeRow(AuditColumns, Base):
    """Action 유형. 기본 유형(시드)은 생성자가 없고 default_order를 가진다."""

    __tablename__ = "action_types"

    name: Mapped[str] = mapped_column(String(50))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    default_order: Mapped[int | None] = mapped_column(Integer, default=None)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )

    __table_args__ = (
        CheckConstraint("is_default = (default_order is not null)", name="default_order"),
        Index("uq_action_types_name_lower", func.lower(name), unique=True),
        Index("ix_action_types_created_by_user_id", "created_by_user_id"),
    )


class VendorRow(AuditColumns, Base):
    """Vendor. 이름은 대소문자 무시로 고유하다."""

    __tablename__ = "vendors"

    name: Mapped[str] = mapped_column(String(100))

    __table_args__ = (Index("uq_vendors_name_lower", func.lower(name), unique=True),)


class SolutionRow(AuditColumns, Base):
    """Vendor 소속 Solution. Vendor를 지우면 함께 지워지고, 이름은 Vendor 안에서 고유하다."""

    __tablename__ = "solutions"

    vendor_id: Mapped[UUID] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))

    __table_args__ = (
        # Deal의 복합 FK(solution_id, vendor_id)가 가리키려면 인덱스가 아니라 제약이어야 한다.
        UniqueConstraint("id", "vendor_id", name="uq_solutions_id_vendor_id"),
        Index("uq_solutions_vendor_id_name_lower", "vendor_id", func.lower(name), unique=True),
    )
