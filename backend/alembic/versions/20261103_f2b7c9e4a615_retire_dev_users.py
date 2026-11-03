"""retire_dev_users: 예전 개발 로그인 사용자 3명(dev-admin·dev-sales·dev-user)과 참조 데이터 삭제

Revision ID: f2b7c9e4a615
Revises: d9a4e6b2f581
Create Date: 2026-11-03 14:00:00.000000

`lower(login_id) IN ('dev-admin','dev-sales','dev-user')` 사용자(예전 개발 로그인이 만든 세 아이디만 대상,
`dev-ops` 같은 다른 `dev-` 아이디는 일반 사용자라 건드리지 않는다)와 그 사용자를 참조하는 모든 데이터를 한 트랜잭션에서
자식 -> 부모 순서로 지운다(사용자 결정: 데이터도 함께 삭제, SET NULL 우회 없음).
users를 참조하는 FK 전수(information_schema 기준, 2026-11-03):
  action_types.created_by_user_id, alert_settings.updated_by_user_id, auth_sessions.user_id,
  bant_labels.created_by_user_id, deal_actions.actor_user_id, deal_attachments.uploaded_by_user_id,
  deal_history.changed_by_user_id, deals.owner_user_id, directory_settings.updated_by_user_id,
  forecast_snapshot_cells.owner_user_id, partner_meetings.created_by_user_id,
  reports.owner_user_id·updated_by_user_id, storage_settings.updated_by_user_id,
  user_password_hashes.user_id(CASCADE), users.created_by_user_id.
auth_settings·login_failures는 users를 참조하지 않는다(login_failures 키는 해시라 지울 수 없다).
간접 참조: dev가 만든 action_types를 쓰는 deal_actions, dev가 만든 bant_labels를 쓰는
deal_bant_labels도 함께 지운다. dev가 아닌 사용자의 created_by가 dev를 가리키면 그 사용자는
지우지 않고 자기 자신을 가리키게 한다(최초 admin과 같은 규칙).
대상 행이 없으면 아무것도 바꾸지 않는다(product에서도 개발 로그인이 항상 거부되어 이 세 아이디가
만들어진 적이 없으므로 사실상 no-op). offline(--sql) 모드는 데이터를 조회할 수 없어 건너뛰며 경고를 남긴다. 지운 첨부 파일은 디스크에 남으므로 WARNING 로그로
저장 위치와 storage_key를 남긴다. downgrade는 지원하지 않고 복구는 백업 복원뿐이다.
"""

# ruff: noqa: S608  (SQL은 모두 이 파일의 상수 조합이고 외부 입력이 없다)
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import context, op


# revision identifiers, used by Alembic.
revision: str = "f2b7c9e4a615"
down_revision: Union[str, Sequence[str], None] = "d9a4e6b2f581"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOG = logging.getLogger("alembic.retire_dev_users")

_DEV_IDS = "('dev-admin', 'dev-sales', 'dev-user')"
_DEV = f"SELECT id FROM users WHERE lower(login_id) IN {_DEV_IDS}"
_DEV_TYPES = f"SELECT id FROM action_types WHERE created_by_user_id IN ({_DEV})"
_DEV_LABELS = f"SELECT id FROM bant_labels WHERE created_by_user_id IN ({_DEV})"
_DEV_DEALS = f"SELECT id FROM deals WHERE owner_user_id IN ({_DEV})"

# 자식 -> 부모 순서
_DELETES: tuple[str, ...] = (
    f"DELETE FROM deal_actions WHERE actor_user_id IN ({_DEV}) "
    f"OR action_type_id IN ({_DEV_TYPES}) OR deal_id IN ({_DEV_DEALS})",
    f"DELETE FROM deal_history WHERE changed_by_user_id IN ({_DEV}) OR deal_id IN ({_DEV_DEALS})",
    f"DELETE FROM deal_attachments WHERE uploaded_by_user_id IN ({_DEV}) "
    f"OR deal_id IN ({_DEV_DEALS})",
    f"DELETE FROM deal_bant_labels WHERE label_id IN ({_DEV_LABELS}) OR deal_id IN ({_DEV_DEALS})",
    f"DELETE FROM deal_partners WHERE deal_id IN ({_DEV_DEALS})",
    f"DELETE FROM deals WHERE owner_user_id IN ({_DEV})",
    f"DELETE FROM action_types WHERE created_by_user_id IN ({_DEV})",
    f"DELETE FROM bant_labels WHERE created_by_user_id IN ({_DEV})",
    f"DELETE FROM forecast_snapshot_cells WHERE owner_user_id IN ({_DEV})",
    f"DELETE FROM reports WHERE owner_user_id IN ({_DEV}) OR updated_by_user_id IN ({_DEV})",
    f"DELETE FROM partner_meetings WHERE created_by_user_id IN ({_DEV})",
    f"DELETE FROM auth_sessions WHERE user_id IN ({_DEV})",
    f"DELETE FROM user_password_hashes WHERE user_id IN ({_DEV})",
    f"DELETE FROM alert_settings WHERE updated_by_user_id IN ({_DEV})",
    f"DELETE FROM directory_settings WHERE updated_by_user_id IN ({_DEV})",
    f"DELETE FROM storage_settings WHERE updated_by_user_id IN ({_DEV})",
    f"UPDATE users SET created_by_user_id = id WHERE lower(login_id) NOT IN {_DEV_IDS} "
    f"AND created_by_user_id IN ({_DEV})",
    f"DELETE FROM users WHERE lower(login_id) IN {_DEV_IDS}",
)


def _warn_attachments(bind: sa.Connection) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT a.storage_key FROM deal_attachments a "
            f"WHERE a.uploaded_by_user_id IN ({_DEV}) OR a.deal_id IN ({_DEV_DEALS})"
        )
    ).all()
    if not rows:
        return
    path = bind.execute(sa.text("SELECT path FROM storage_settings WHERE id = 1")).scalar()
    _LOG.warning(
        "삭제된 첨부 %d건의 파일이 저장 위치 %s 아래에 남아 있습니다. 수동으로 정리하세요(storage_key: %s).",
        len(rows),
        path,
        ", ".join(str(r[0]) for r in rows),
    )


def upgrade() -> None:
    """Upgrade schema."""
    if context.is_offline_mode():
        _LOG.warning(
            "offline(--sql) 모드에서는 dev 로그인 사용자 삭제를 건너뜁니다. 온라인으로 적용하세요."
        )
        return
    bind = op.get_bind()
    if bind.execute(sa.text(f"SELECT count(*) FROM ({_DEV}) d")).scalar() == 0:
        return
    _warn_attachments(bind)
    for statement in _DELETES:
        bind.execute(sa.text(statement))


def downgrade() -> None:
    """Downgrade는 지원하지 않는다. 복구는 백업 복원뿐이다."""
    raise RuntimeError(
        "삭제된 개발용 세 아이디의 사용자와 참조 데이터는 복구할 수 없어 downgrade를 지원하지 않습니다. "
        "배포 전 백업을 복원하세요."
    )
