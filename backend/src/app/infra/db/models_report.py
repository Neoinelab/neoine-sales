"""저장 리포트 ORM 모델. models.py 끝에서 import해 등록한다.

definition은 검증을 통과한 원시 정의 JSON, generated_sql은 표시용 문자열이다. 결과 데이터는 저장하지
않는다. chart는 차트 설정 JSON이며 차트가 없으면 NULL이다.
layout은 결과 배치 JSON이며 NULL이면 기본 배치로 읽는다.
"""

from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.saved_report.values import REPORT_DESCRIPTION_MAX, REPORT_NAME_MAX, ReportVisibility
from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_VISIBILITIES = ", ".join(f"'{member.value}'" for member in ReportVisibility)


class ReportRow(AuditColumns, Base):
    """저장 리포트. 이름은 전체에서 대소문자 무시로 고유하다."""

    __tablename__ = "reports"

    name: Mapped[str] = mapped_column(String(REPORT_NAME_MAX))
    description: Mapped[str] = mapped_column(String(REPORT_DESCRIPTION_MAX))
    visibility: Mapped[str] = mapped_column(String(10))
    owner_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    updated_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    generated_sql: Mapped[str] = mapped_column(Text)
    chart: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    layout: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    revision: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(f"visibility in ({_VISIBILITIES})", name="visibility_valid"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint("jsonb_typeof(definition) = 'object'", name="definition_object"),
        CheckConstraint("layout is null or jsonb_typeof(layout) = 'object'", name="layout_object"),
        Index("uq_reports_name_lower", func.lower(name), unique=True),
        Index("ix_reports_owner_user_id", "owner_user_id"),
        Index("ix_reports_updated_by_user_id", "updated_by_user_id"),
    )
