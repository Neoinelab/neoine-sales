"""Deal Comment ORM 모델: Deal에 연결되고 선택적으로 그 Deal의 Action 하나에 연결된다.

Action 연결은 복합 FK `(action_id, deal_id) -> deal_actions(id, deal_id)`라 다른 Deal의 Action을
가리킬 수 없다(deal_actions의 `uq_deal_actions_id`가 대상). Action·Deal을 지우면 함께 지워진다.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.models import AuditColumns


class DealCommentRow(AuditColumns, Base):
    __tablename__ = "deal_comments"

    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id", ondelete="CASCADE"))
    action_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    author_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="RESTRICT")
    )
    body: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        CheckConstraint("btrim(body) <> ''", name="body_not_blank"),
        CheckConstraint("read_at IS NULL OR read_at >= created_at", name="read_after_created"),
        ForeignKeyConstraint(
            ["action_id", "deal_id"],
            ["deal_actions.id", "deal_actions.deal_id"],
            name="fk_deal_comments_action_id_deal_actions",
            ondelete="CASCADE",
        ),
        Index("ix_deal_comments_deal_id_created_at", "deal_id", "created_at"),
        Index("ix_deal_comments_action_id", "action_id"),
        Index("ix_deal_comments_author_user_id", "author_user_id"),
        Index(
            "ix_deal_comments_deal_id_unread",
            "deal_id",
            "action_id",
            postgresql_where=text("read_at IS NULL"),
        ),
    )
