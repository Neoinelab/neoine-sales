"""모든 테이블의 deleted_at 제거(소프트 삭제 폐지), users 로그인 아이디 유니크 인덱스 교체

Revision ID: f4b8d2a6c9e1
Revises: e3a9c41b7d52
Create Date: 2026-10-13 14:00:00.000000

대상: customers, partners, deals, deal_actions, users. 삭제는 물리 삭제로 통일되었다.

안전장치: 5개 테이블을 ACCESS EXCLUSIVE로 잠근 뒤 deleted_at이 설정된 행을 센다. 하나라도 있으면
데이터를 지우지 않고 ``<테이블>=<건수>``를 담은 RuntimeError로 중단한다(DDL 이전이므로 스키마 변화 없음).
사람이 확인·정리한 뒤 다시 실행한다. 이 리비전은 데이터를 자동으로 삭제하지 않는다.

순서(한 트랜잭션): 사전 점검 -> uq_users_login_id(lower(login_id), 일반 유니크) 생성 ->
부분 유니크 uq_users_login_id_active 삭제 -> 5개 컬럼 drop.

호환성(contract 단계, expand/contract 예외): 구 앱은 5개 테이블 모두 deleted_at을 읽고 써서 이 스키마와
비호환이다. 앱과 마이그레이션을 같은 배포로 내보낸다. 새 앱은 컬럼이 남은 구 스키마에서도 동작하지만
삭제 표시 행이 다시 보이므로 반드시 사전 점검을 통과한 뒤 배포한다.

롤백: 사용자 확인 후 ``alembic downgrade -1`` + 이전 빌드 재배포. downgrade는 nullable deleted_at과
부분 유니크 인덱스를 되돌리지만, 새 버전에서 물리 삭제된 행은 복원되지 않는다. product는 적용 전
``pg_dump`` 백업을 권장한다.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4b8d2a6c9e1"
down_revision: Union[str, Sequence[str], None] = "e3a9c41b7d52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 고정 순서로 잠가 교착을 피한다. 값은 상수이므로 SQL에 직접 쓴다.
_TABLES = ("customers", "partners", "deals", "deal_actions", "users")


def _lower_login_id() -> sa.ColumnClause[str]:
    return sa.literal_column("lower(login_id)")


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    for table in _TABLES:
        connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    marked = {}
    for table in _TABLES:
        count = connection.execute(
            sa.text(f"SELECT count(*) FROM {table} WHERE deleted_at IS NOT NULL")  # noqa: S608
        ).scalar_one()
        if count:
            marked[table] = int(count)
    if marked:
        detail = ", ".join(f"{table}={count}" for table, count in marked.items())
        raise RuntimeError(
            "deleted_at이 설정된 행이 있어 중단합니다(데이터는 지우지 않았고 스키마도 그대로입니다): "
            f"{detail}. 먼저 사람이 확인·정리한 뒤 다시 실행하세요."
        )

    op.create_index("uq_users_login_id", "users", [_lower_login_id()], unique=True)
    op.drop_index(
        "uq_users_login_id_active", table_name="users", postgresql_where="deleted_at IS NULL"
    )
    for table in _TABLES:
        op.drop_column(table, "deleted_at")


def downgrade() -> None:
    """Downgrade schema. 새 버전에서 물리 삭제된 행은 복원되지 않는다."""
    for table in _TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "uq_users_login_id_active",
        "users",
        [_lower_login_id()],
        unique=True,
        postgresql_where="deleted_at IS NULL",
    )
    op.drop_index("uq_users_login_id", table_name="users")
