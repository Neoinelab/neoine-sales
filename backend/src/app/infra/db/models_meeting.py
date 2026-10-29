"""파트너 미팅 기록 ORM 모델. models.py 끝에서 import해 등록한다."""

from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.models import AuditColumns


class PartnerMeetingRow(AuditColumns, Base):
    """파트너 회사와의 미팅 기록. Deal을 지우면 함께 지워진다(CASCADE)."""

    __tablename__ = "partner_meetings"

    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    partner_company: Mapped[str] = mapped_column(String(200))
    meeting_date: Mapped[date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )

    __table_args__ = (
        CheckConstraint(r"partner_company <> '' and partner_company !~ '\s'", name="company_valid"),
        CheckConstraint(r"content ~ '\S'", name="content_not_blank"),
        Index("ix_partner_meetings_meeting_date_id", "meeting_date", "id"),
        Index("ix_partner_meetings_deal_id", "deal_id"),
        Index("ix_partner_meetings_created_by_user_id", "created_by_user_id"),
    )
