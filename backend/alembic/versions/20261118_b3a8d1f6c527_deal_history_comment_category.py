"""deal_history 구분에 comment 추가: CHECK ck_deal_history_category 재생성

Revision ID: b3a8d1f6c527
Revises: e7c1a5b9d482
Create Date: 2026-11-18 09:00:00.000000

CHECK 허용 값을 12개에서 13개('comment' 추가)로 넓힌다. 데이터 변경 없음(순수 expand).
downgrade는 comment 행이 있으면 건수와 함께 중단하고(행 삭제·변경 없음) 없을 때만 12개로 되돌린다.
코드만 롤백해도 구 앱은 comment 행을 쓰지 않는다. product 적용은 배포 전 pg_dump 후 사람 승인.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3a8d1f6c527"
down_revision: Union[str, Sequence[str], None] = "e7c1a5b9d482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASE = (
    "'created', 'status', 'forecast', 'amount', 'expectedClose', 'owner', 'partner', "
    "'contact', 'bant', 'action', 'attachment'"
)
_NEW = f"(category in ({_BASE}, 'comment', 'other'))"
_OLD = f"(category in ({_BASE}, 'other'))"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_deal_history_category"), "deal_history", type_="check")
    op.create_check_constraint(op.f("ck_deal_history_category"), "deal_history", _NEW)


def downgrade() -> None:
    rows = (
        op.get_bind()
        .execute(sa.text("select count(*) from deal_history where category = 'comment'"))
        .scalar_one()
    )
    if rows:
        raise RuntimeError(
            f"deal_history에 comment 행 {rows}건이 있어 downgrade할 수 없습니다(행은 삭제하지 않음)."
        )
    op.drop_constraint(op.f("ck_deal_history_category"), "deal_history", type_="check")
    op.create_check_constraint(op.f("ck_deal_history_category"), "deal_history", _OLD)
