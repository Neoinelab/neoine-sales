"""Forecast 월말 스냅숏 ORM 모델(P6 R2). models.py 끝에서 import해 등록한다.

헤더(기준 월·생성 시각) + 열(그 시점 Forecast 코드 목록) + 셀(Deal이 있는 칸). 셀은
`(snapshot_id, forecast_key)` 복합 FK(CASCADE)로 열을 참조해 key가 항상 같은 스냅숏의 열에 있음을
DB가 보장한다(헤더로 가는 직접 FK는 없다). 코드 테이블은 FK로 참조하지 않는다(과거 기록 보존).
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base, identity_key


class ForecastSnapshotRow(Base):
    __tablename__ = "forecast_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    snapshot_year: Mapped[int] = mapped_column(Integer)
    snapshot_month: Mapped[int] = mapped_column(Integer)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("snapshot_year", "snapshot_month"),
        CheckConstraint("snapshot_month BETWEEN 1 AND 12", name="snapshot_month_range"),
    )


class ForecastSnapshotColumnRow(Base):
    __tablename__ = "forecast_snapshot_columns"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("forecast_snapshots.id", ondelete="CASCADE")
    )
    forecast_key: Mapped[str] = mapped_column(String(50))
    forecast_name: Mapped[str] = mapped_column(String(50))
    forecast_outcome: Mapped[str] = mapped_column(String(10))
    forecast_order: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("snapshot_id", "forecast_key"),
        CheckConstraint(
            "forecast_outcome IN ('open', 'won', 'lost')", name="forecast_outcome_valid"
        ),
    )


class ForecastSnapshotCellRow(Base):
    __tablename__ = "forecast_snapshot_cells"

    id: Mapped[int] = mapped_column(BigInteger, identity_key(), primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(BigInteger)
    revenue_year: Mapped[int] = mapped_column(Integer)
    revenue_month: Mapped[int] = mapped_column(Integer)
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    forecast_key: Mapped[str] = mapped_column(String(50))
    deal_count: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "forecast_key"],
            ["forecast_snapshot_columns.snapshot_id", "forecast_snapshot_columns.forecast_key"],
            ondelete="CASCADE",
            # 규칙대로면 64자라 PostgreSQL 식별자 한도(63자)를 넘으므로 이름을 직접 정한다.
            name="fk_forecast_snapshot_cells_snapshot_id_snapshot_columns",
        ),
        UniqueConstraint(
            "snapshot_id", "revenue_year", "revenue_month", "owner_user_id", "forecast_key"
        ),
        CheckConstraint("revenue_month BETWEEN 1 AND 12", name="revenue_month_range"),
        CheckConstraint("deal_count >= 1", name="deal_count_positive"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        Index("ix_forecast_snapshot_cells_owner_user_id", "owner_user_id"),
    )
