"""마이그레이션 리비전 상수. 과거 리비전 검증 테스트는 head 대신 이 상수로 target을 고정한다.

head는 계속 앞으로 간다. 과거 리비전의 스키마(예: deals.owner 문자열 컬럼)를 전제하는 테스트가
새 리비전 때문에 깨지거나 새 리비전의 변환에 걸리지 않도록 target을 고정해 보호한다.
"""

from typing import Final

STAGE_REVISION: Final = "2a49cc41cdff"  # deal_stage + deal_stage_changes
OWNER_REVISION: Final = "39d531ff2643"  # deals.owner_user_id(등록자 subject, 문자열)
AUTH_REVISION: Final = "dd7f21f7190e"  # users·login_failures·directory_settings
HISTORY_REVISION: Final = "e3a9c41b7d52"  # 활동 이력 필드
DROP_DELETED_AT_REVISION: Final = (
    "f4b8d2a6c9e1"  # 모든 테이블 deleted_at 제거(= 사용자 FK 이전 head)
)
LEGACY_HEAD: Final = DROP_DELETED_AT_REVISION
USER_FK_REVISION: Final = "0d248153ec93"  # 사용자 참조를 users.id FK로 통일(= 코드·Label 이전 head)
CODES_REVISION: Final = "c5d8e2f4a916"  # codes + bant_labels + 기본값 시드(= 연락처 통합 이전 head)


CONTACTS_REVISION: Final = "66ebcb3da2da"  # 연락처 통합(= P1 Deal 모델 이전 head)


def deal_model_revision() -> str:
    """P1 Deal 모델 재구성(M-P1 `deal_model_v2`) 리비전 id: CONTACTS_REVISION 바로 다음 리비전이다.

    id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는
    이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == CONTACTS_REVISION]
    assert len(children) == 1, f"CONTACTS_REVISION 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def action_snapshot_revision() -> str:
    """P2 Action 스냅숏(M-P2 `action_snapshot`) 리비전 id: M-P1(`deal_model_revision()`) 바로 다음.

    id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는
    이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = deal_model_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"M-P1 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def attachments_revision() -> str:
    """P2b 첨부 파일(M-P2b `attachments`) 리비전 id: M-P2(`action_snapshot_revision()`) 바로 다음.

    storage_settings·deal_attachments 두 테이블을 만드는 단일 리비전이다. id는 구현이 정하므로
    그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = action_snapshot_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"M-P2 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def contacts_revision() -> str:
    """연락처 통합(R2) 리비전 id: CODES_REVISION 바로 다음의 리비전이다(id는 구현이 정한다).

    상수 대신 그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == CODES_REVISION]
    assert len(children) == 1, f"CODES_REVISION 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def alert_settings_revision() -> str:
    """P3 경고 기준·Status 진입(M-P3 `alert_settings`) 리비전 id: M-P2b 바로 다음.

    alert_settings 테이블과 deals.status_changed_at을 만드는 단일 리비전이다. id는 구현이 정하므로
    그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = attachments_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"M-P2b 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def vendor_solution_revision() -> str:
    """Vendor·Solution 관리(`vendors_solutions`) 리비전 id: M-P3 바로 다음.

    vendors·solutions 테이블을 만들고 deals.vendor/solution 텍스트 컬럼을 vendor_id/solution_id FK로
    바꾸는 단일 리비전이다. id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면
    AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = alert_settings_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"M-P3 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def action_types_revision() -> str:
    """Action 유형(`action_types`) 리비전 id: Vendor·Solution 리비전 바로 다음이고 head다.

    action_types 테이블(기본 유형 8개 시드)을 만들고, deal_actions 행을 지우고, action_type 컬럼을
    action_type_id FK로 바꾸는 단일 리비전이다. id는 구현이 정하므로 그래프에서 찾는다. 없거나
    둘 이상이면 AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = vendor_solution_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"Vendor·Solution 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def next_action_status_revision() -> str:
    """Next Action 상태(`next_action_status`) 리비전 id: Action 유형 리비전 바로 다음이고 head다.

    deal_actions의 action·next_action·due_date를 NULL 허용으로 바꾸고 next_action_status·
    next_action_closed_at 컬럼과 CHECK 4개를 추가하는 단일 리비전이다. id는 구현이 정하므로
    그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = action_types_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"Action 유형 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def deals_users_required_revision() -> str:
    """Deal users 필수 리비전 id: Next Action 상태 리비전 바로 다음이고 head다.

    users가 NULL인 행을 0으로 채우고 CHECK를 `users >= 0`으로 바꾸고 NOT NULL로 만드는 단일
    리비전이다. id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면 AssertionError
    (구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = next_action_status_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"Next Action 상태 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def bigint_ids_revision() -> str:
    """BIGINT id 리비전(`bigint_ids`) id: Deal users 필수 리비전(`e8c2b4f6a1d9`) 다음이고 head다.

    모든 앱 테이블을 가드 없이 drop하고 BIGINT IDENTITY 스키마로 다시 만든 뒤 기본 시드(코드 13,
    BANT Label 23, Action 유형 8)를 넣는 단일 리비전이다. downgrade는 RuntimeError로 거부한다.
    id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면 AssertionError(구현 전에는 이것이
    red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = deals_users_required_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"Deal users 필수 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]


def forecast_snapshots_revision() -> str:
    """Forecast 월말 스냅숏(P6 R2 `forecast_snapshots`) 리비전 id: BIGINT id 리비전 다음이고 head다.

    forecast_snapshots·forecast_snapshot_columns·forecast_snapshot_cells 세 테이블만 추가하는 순수
    expand 단일 리비전이다
    (기존 테이블은 건드리지 않는다). id는 구현이 정하므로 그래프에서 찾는다. 없거나 둘 이상이면
    AssertionError(구현 전에는 이것이 red다).
    """
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    from tests.support.database import _alembic_config  # noqa: PLC0415

    previous = bigint_ids_revision()
    script = ScriptDirectory.from_config(_alembic_config())
    children = [r.revision for r in script.walk_revisions() if r.down_revision == previous]
    assert len(children) == 1, f"BIGINT id 다음 리비전이 정확히 하나여야 한다: {children}"
    return children[0]
