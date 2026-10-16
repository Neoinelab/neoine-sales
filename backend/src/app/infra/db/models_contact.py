"""연락처(고객·파트너 통합) ORM 모델. models.py 끝에서 import해 등록한다."""

from sqlalchemy import CheckConstraint, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.contact.values import ContactKind
from app.infra.db.base import Base
from app.infra.db.models import AuditColumns

_KINDS = ", ".join(f"'{kind.value}'" for kind in ContactKind)
# 공백 문자(\s)가 없어야 한다. NULL은 비교 결과가 NULL이라 CHECK를 통과한다.
_NO_SPACE = r"company !~ '\s' and name !~ '\s' and email !~ '\s' and phone !~ '\s'"


class ContactRow(AuditColumns, Base):
    """고객·파트너 연락처. 같은 사람의 중복 방지는 유스케이스의 잠금과 재확인이 맡는다."""

    __tablename__ = "contacts"

    kind: Mapped[str] = mapped_column(String(10))
    company: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(100), default=None)
    email: Mapped[str | None] = mapped_column(String(254), default=None)
    phone: Mapped[str | None] = mapped_column(String(40), default=None)

    __table_args__ = (
        CheckConstraint(f"kind in ({_KINDS})", name="kind_valid"),
        CheckConstraint(_NO_SPACE, name="no_space"),
        Index("ix_contacts_kind_company_lower", "kind", func.lower(company)),
        Index("ix_contacts_identity", "kind", func.lower(company), func.lower(name)),
        Index("ix_contacts_created_at_id", "created_at", "id"),
    )
