"""partner_meetings: 파트너 미팅 기록 테이블 추가(순수 expand)

Revision ID: c4e8a1d7f203
Revises: b7d2e9a4c156
Create Date: 2026-10-28 15:00:00.000000

기존 테이블·컬럼을 건드리지 않고 partner_meetings 1개만 추가한다. 구 앱과 같은 DB에서 공존하고
데이터는 손상되지 않지만, 코드만 롤백하면 두 가지가 달라진다: Deal 삭제는 미팅도 함께 지우고
(CASCADE, 건수 안내 없음), 미팅을 쓴 사용자를 삭제하면 구 앱이 이 FK를 몰라 퇴사 처리 대신
500이 난다. downgrade는 테이블을 지운다(미팅 기록 소실).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4e8a1d7f203"
down_revision: Union[str, Sequence[str], None] = "b7d2e9a4c156"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "partner_meetings",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(always=False, start=1, increment=1, maxvalue=9007199254740991),
            nullable=False,
        ),
        sa.Column("deal_id", sa.BigInteger(), nullable=False),
        sa.Column("partner_company", sa.String(length=200), nullable=False),
        sa.Column("meeting_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "partner_company <> '' and partner_company !~ '\\s'",
            name=op.f("ck_partner_meetings_company_valid"),
        ),
        sa.CheckConstraint("content ~ '\\S'", name=op.f("ck_partner_meetings_content_not_blank")),
        sa.ForeignKeyConstraint(
            ["deal_id"],
            ["deals.id"],
            name=op.f("fk_partner_meetings_deal_id_deals"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_partner_meetings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_meetings")),
    )
    op.create_index(
        "ix_partner_meetings_meeting_date_id", "partner_meetings", ["meeting_date", "id"]
    )
    op.create_index("ix_partner_meetings_deal_id", "partner_meetings", ["deal_id"])
    op.create_index(
        "ix_partner_meetings_created_by_user_id", "partner_meetings", ["created_by_user_id"]
    )


def downgrade() -> None:
    """Downgrade schema. 미팅 기록이 모두 사라진다."""
    op.drop_index("ix_partner_meetings_created_by_user_id", table_name="partner_meetings")
    op.drop_index("ix_partner_meetings_deal_id", table_name="partner_meetings")
    op.drop_index("ix_partner_meetings_meeting_date_id", table_name="partner_meetings")
    op.drop_table("partner_meetings")
