"""Comment 읽음(Owner 기준): deal_comments.read_at, CHECK, 읽지 않음 부분 인덱스

Revision ID: e7c1a5b9d482
Revises: d2f6b8a4c931
Create Date: 2026-11-17 12:00:00.000000

순수 expand. read_at 추가 후 기존 행은 모두 읽음으로(read_at = created_at) 채운다. 행 삭제 없음.
downgrade는 인덱스·CHECK·컬럼을 drop(읽음 시각만 사라진다). 코드만 롤백하면 구 앱은 read_at을
무시한다. product 적용은 배포 전 pg_dump 후 사람 승인.
"""

import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7c1a5b9d482"
down_revision: Union[str, Sequence[str], None] = "d2f6b8a4c931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOG = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.add_column("deal_comments", sa.Column("read_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(sa.text("UPDATE deal_comments SET read_at = created_at"))
    op.create_check_constraint(
        "read_after_created", "deal_comments", "read_at IS NULL OR read_at >= created_at"
    )
    op.create_index(
        "ix_deal_comments_deal_id_unread",
        "deal_comments",
        ["deal_id", "action_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )


def downgrade() -> None:
    read_rows = (
        op.get_bind()
        .execute(sa.text("select count(*) from deal_comments where read_at is not null"))
        .scalar_one()
    )
    _LOG.warning("downgrade로 Comment 읽음 시각(read_at) %s건이 사라집니다.", read_rows)
    op.drop_index("ix_deal_comments_deal_id_unread", table_name="deal_comments")
    op.drop_constraint(op.f("ck_deal_comments_read_after_created"), "deal_comments", type_="check")
    op.drop_column("deal_comments", "read_at")
