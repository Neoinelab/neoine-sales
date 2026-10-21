"""deals_users_required: deals.users 필수화(0 이상)

Revision ID: e8c2b4f6a1d9
Revises: c7f1a9d3e5b2
Create Date: 2026-10-21 10:00:00.000000

사용자 결정(2026-10-21): Deal의 Users를 필수 입력(0 이상 정수)으로 바꾼다.
upgrade: users가 NULL인 행을 0으로 채우고(updated_at은 바꾸지 않는다) CHECK를
`users >= 0`으로 재생성한 뒤 NOT NULL로 만든다. 사전 중단 점검은 없다(사용자 결정).

expand/contract 원칙의 예외: 구 앱은 NULL users로 INSERT하므로 이 리비전 이후 실패하고,
0 값을 읽지도 못한다(구 `check_users`가 1 미만을 거절 -> `deal_mapping._details`의
DealDetails 생성 실패 -> 0이 된 Deal이 포함된 목록·상세 조회 실패). 재시작 전에 떠 있는
구 앱이나, `deploy.sh` 헬스체크 실패 시 코드만 되돌리는 자동 롤백에서 발생한다.
따라서 자동 롤백 뒤에는 사람이 즉시 `alembic downgrade -1`을 실행해야 한다.
앱과 같은 배포를 전제로 하며 product 적용 전 백업을 권장한다.

downgrade: NULL을 허용하고 users = 0인 행을 NULL로 되돌린 뒤 CHECK를
`users is null or users >= 1`로 복원한다. 한계: 사용자가 직접 입력한 0도 NULL이 된다.
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8c2b4f6a1d9"
down_revision: Union[str, Sequence[str], None] = "c7f1a9d3e5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CHECK = "ck_deals_users_positive"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("LOCK TABLE deals IN ACCESS EXCLUSIVE MODE")
    op.execute("UPDATE deals SET users = 0 WHERE users IS NULL")
    op.drop_constraint(op.f(_CHECK), "deals", type_="check")
    op.create_check_constraint("users_positive", "deals", "users >= 0")
    op.alter_column("deals", "users", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("LOCK TABLE deals IN ACCESS EXCLUSIVE MODE")
    op.alter_column("deals", "users", nullable=True)
    op.execute("UPDATE deals SET users = NULL WHERE users = 0")
    op.drop_constraint(op.f(_CHECK), "deals", type_="check")
    op.create_check_constraint("users_positive", "deals", "users is null or users >= 1")
