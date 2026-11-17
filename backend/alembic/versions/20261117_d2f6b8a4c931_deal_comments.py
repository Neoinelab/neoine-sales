"""Action Memo를 Deal Comment로 분리: deal_comments 신설, 기존 Memo 복사, deal_actions.memo 제거

Revision ID: d2f6b8a4c931
Revises: a9d3f5c7e214
Create Date: 2026-11-17 00:00:00.000000

한 트랜잭션에서 ① uq_deal_actions_id 추가 ② deal_comments 생성 ③ 비지 않은 Memo를 Action Comment로
복사(작성자·시각은 Action의 것) ④ 복사 건수 점검(다르면 RuntimeError로 전부 롤백) ⑤ memo drop.
비지 않은 값은 모두 옮겨진 뒤라 정보가 남는다(빈 값만 버림, 2026-11-17 사용자 승인 contract).
downgrade는 Action 연결 Comment를 오래된 순 줄바꿈으로 이어 memo를 채운다. Deal Comment 전부와
Action Comment의 작성자·작성 시각은 되살릴 수 없다. 코드만 롤백하면 구 앱이 memo를 읽다 실패하므로
downgrade -1을 함께 한다. product 적용은 배포 전 pg_dump 후 사람 승인.
"""

import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f6b8a4c931"
down_revision: Union[str, Sequence[str], None] = "a9d3f5c7e214"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOG = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    op.create_unique_constraint("uq_deal_actions_id", "deal_actions", ["id", "deal_id"])
    op.create_table(
        "deal_comments",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("action_id", sa.BigInteger(), nullable=True),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("btrim(body) <> ''", name=op.f("ck_deal_comments_body_not_blank")),
        sa.ForeignKeyConstraint(
            ["action_id", "deal_id"],
            ["deal_actions.id", "deal_actions.deal_id"],
            name="fk_deal_comments_action_id_deal_actions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            name=op.f("fk_deal_comments_author_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_deal_comments_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_comments")),
    )
    op.create_index(
        "ix_deal_comments_deal_id_created_at", "deal_comments", ["deal_id", "created_at"]
    )
    op.create_index("ix_deal_comments_action_id", "deal_comments", ["action_id"])
    op.create_index("ix_deal_comments_author_user_id", "deal_comments", ["author_user_id"])

    op.execute(
        sa.text(
            "insert into deal_comments"
            " (deal_id, action_id, author_user_id, body, created_at, updated_at)"
            " select deal_id, id, actor_user_id, memo, created_at, updated_at"
            " from deal_actions where btrim(memo) <> '' order by id"
        )
    )

    bind = op.get_bind()
    expected = int(
        bind.execute(
            sa.text("select count(*) from deal_actions where btrim(memo) <> ''")
        ).scalar_one()
    )
    copied = int(bind.execute(sa.text("select count(*) from deal_comments")).scalar_one())
    if copied != expected:
        raise RuntimeError(
            f"Memo를 Comment로 옮긴 건수({copied})가 Memo가 있는 Action 수({expected})와 다릅니다."
        )

    op.drop_column("deal_actions", "memo")


def downgrade() -> None:
    op.add_column(
        "deal_actions",
        sa.Column("memo", sa.Text(), server_default=sa.text("''"), nullable=False),
    )
    op.execute(
        """
        update deal_actions set memo = joined.body
        from (
            select action_id, string_agg(body, E'\\n' order by created_at, id) as body
            from deal_comments where action_id is not null group by action_id
        ) as joined
        where joined.action_id = deal_actions.id
        """
    )
    op.alter_column("deal_actions", "memo", server_default=None)
    lost = (
        op.get_bind()
        .execute(sa.text("select count(*) from deal_comments where action_id is null"))
        .scalar_one()
    )
    _LOG.warning(
        "downgrade로 Deal Comment %s건이 소실됩니다. Action Comment의 작성자·작성 시각도 "
        "복원되지 않고 Action당 여러 건은 memo 하나로 합쳐집니다.",
        lost,
    )
    op.drop_index("ix_deal_comments_author_user_id", table_name="deal_comments")
    op.drop_index("ix_deal_comments_action_id", table_name="deal_comments")
    op.drop_index("ix_deal_comments_deal_id_created_at", table_name="deal_comments")
    op.drop_table("deal_comments")
    op.drop_constraint("uq_deal_actions_id", "deal_actions", type_="unique")
