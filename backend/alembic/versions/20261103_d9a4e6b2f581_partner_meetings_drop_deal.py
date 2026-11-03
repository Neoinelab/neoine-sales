"""partner_meetings_drop_deal: 파트너 미팅에서 Deal 연결(deal_id) 제거

Revision ID: d9a4e6b2f581
Revises: af477447ba9f
Create Date: 2026-11-03 10:00:00.000000

기존 미팅 행은 지우지 않고 deal_id 컬럼(FK·인덱스 포함)만 drop한다. 구 앱은 deal_id를 필수로
INSERT·SELECT하므로 앱과 같은 배포가 전제이며(expand/contract 예외, 사용자 결정), 코드만 롤백하면
구 앱의 미팅 조회·등록이 실패한다. 어떤 행이 어느 Deal에 속했는지는 복구할 수 없으므로
downgrade는 지원하지 않고 복구는 배포 전 백업 복원뿐이다.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d9a4e6b2f581"
down_revision: Union[str, Sequence[str], None] = "af477447ba9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_partner_meetings_deal_id", table_name="partner_meetings")
    op.drop_constraint("fk_partner_meetings_deal_id_deals", "partner_meetings", type_="foreignkey")
    op.drop_column("partner_meetings", "deal_id")


def downgrade() -> None:
    """Downgrade는 지원하지 않는다. 복구는 백업 복원뿐이다."""
    raise RuntimeError(
        "partner_meetings.deal_id는 복구할 수 없어 downgrade를 지원하지 않습니다. "
        "배포 전 백업을 복원하세요."
    )
