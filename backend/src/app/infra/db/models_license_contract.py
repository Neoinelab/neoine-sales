"""라이선스 계약과 계약 첨부 ORM 모델. models.py 끝에서 import해 등록한다.

규칙 값(상태·점검주기·기간 단위 문자열)은 domain.license_contract.values의 정본과 같고, CHECK에는
마이그레이션에 고정된 리터럴을 쓴다.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_MAX_FILE_BYTES = 104857600  # models_attachment와 같다(마이그레이션에 고정된 값)
ISSUED_STATUSES = ("issued_new", "issued_renewal")  # 발급 상태(신규·갱신)의 infra 내 유일한 리터럴
_ISSUED = f"status in ({', '.join(repr(value) for value in ISSUED_STATUSES)})"


class LicenseContractRow(AuditColumns, Base):
    """Deal 하나에 딸린 라이선스 계약. Deal을 지우면 함께 지워진다(CASCADE)."""

    __tablename__ = "license_contracts"

    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20))
    license_start: Mapped[date | None] = mapped_column(Date, default=None)
    license_end: Mapped[date | None] = mapped_column(Date, default=None)
    term_amount: Mapped[int | None] = mapped_column(SmallInteger, default=None)
    term_unit: Mapped[str | None] = mapped_column(String(10), default=None)
    tech_owner: Mapped[str] = mapped_column(String(100), default="", server_default=text("''"))
    inspection_cycle: Mapped[str] = mapped_column(
        String(20), default="none", server_default=text("'none'")
    )
    note: Mapped[str] = mapped_column(Text, default="", server_default=text("''"))
    renewed_from_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("license_contracts.id", ondelete="SET NULL"), default=None
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    updated_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        CheckConstraint(
            "status in ('not_issued', 'issued_new', 'issued_renewal', 'ended')", name="status"
        ),
        CheckConstraint(
            "inspection_cycle in ('monthly', 'quarterly', 'semiannual', 'yearly', 'none')",
            name="inspection_cycle",
        ),
        CheckConstraint("term_amount is null or term_amount between 1 and 99", name="term_amount"),
        CheckConstraint("term_unit is null or term_unit in ('month', 'year')", name="term_unit"),
        CheckConstraint(
            "(license_start is null) = (license_end is null)"
            " and (license_start is null) = (term_amount is null)"
            " and (license_start is null) = (term_unit is null)",
            name="term_complete",
        ),
        CheckConstraint(
            "status <> 'not_issued' or license_start is null", name="not_issued_no_term"
        ),
        CheckConstraint(f"not ({_ISSUED}) or license_start is not null", name="issued_has_term"),
        CheckConstraint(
            "license_start is null or license_end >= license_start", name="end_after_start"
        ),
        CheckConstraint("(status = 'ended') = (ended_at is not null)", name="ended_has_time"),
        Index(
            "uq_license_contracts_deal_id_issued",
            "deal_id",
            unique=True,
            postgresql_where=text(_ISSUED),
        ),
        Index("ix_license_contracts_deal_id", "deal_id"),
        Index("ix_license_contracts_license_end_id", "license_end", "id"),
        Index("ix_license_contracts_renewed_from_id", "renewed_from_id"),
        Index("ix_license_contracts_created_by_user_id", "created_by_user_id"),
        Index("ix_license_contracts_updated_by_user_id", "updated_by_user_id"),
    )


class LicenseContractAttachmentRow(AuditColumns, Base):
    """계약 첨부 파일 메타데이터. 계약을 지우면 함께 지워진다(CASCADE). 본문은 디스크에 있다."""

    __tablename__ = "license_contract_attachments"

    contract_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("license_contracts.id", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(100), default="", server_default=text("''"))
    mime: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(32))
    uploaded_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"size_bytes between 0 and {_MAX_FILE_BYTES}", name="size_range"),
        UniqueConstraint(
            "contract_id", "file_name", name="uq_license_contract_attachments_contract_id_file_name"
        ),
        UniqueConstraint("storage_key"),
        Index("ix_license_contract_attachments_uploaded_by_user_id", "uploaded_by_user_id"),
        Index(
            "ix_license_contract_attachments_contract_id_uploaded_at", "contract_id", "uploaded_at"
        ),
    )
