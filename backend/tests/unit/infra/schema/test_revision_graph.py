"""마이그레이션 리비전 그래프: 리비전 체인이 끊기지 않고 head가 하나인지 확인한다(DB 불필요)."""

from alembic.script import ScriptDirectory

from tests.support.database import _alembic_config
from tests.support.drop_deleted_at import PREVIOUS_HEAD as DROP_PREVIOUS_HEAD
from tests.support.revisions import (
    AUTH_REVISION,
    CODES_REVISION,
    CONTACTS_REVISION,
    DROP_DELETED_AT_REVISION,
    HISTORY_REVISION,
    LEGACY_HEAD,
    OWNER_REVISION,
    STAGE_REVISION,
    USER_FK_REVISION,
    action_snapshot_revision,
    action_types_revision,
    alert_settings_revision,
    attachments_revision,
    bigint_ids_revision,
    contacts_revision,
    deal_model_revision,
    deals_users_required_revision,
    directory_service_account_revision,
    forecast_snapshots_revision,
    next_action_status_revision,
    solution_free_text_revision,
    vendor_solution_revision,
)

USERS_REQUIRED_REVISION = "e8c2b4f6a1d9"  # 이 리비전 아래는 UUID 스키마
BIGINT_IDS_REVISION = "a3f7c1d95b28"  # P6 R2 스냅숏 리비전의 down_revision다


FORECAST_SNAPSHOTS_REVISION = "11bfe225caf5"  # Solution 자유 텍스트 리비전의 down_revision이다


SOLUTION_FREE_TEXT_REVISION = "d4b8f6a2c013"  # Reports 리비전의 down_revision다
REPORTS_REVISION = "f1c6a8e2b904"  # 배치 리비전의 down_revision이다
REPORTS_LAYOUT_REVISION = "b7d2e9a4c156"  # 파트너 미팅 리비전의 down_revision이다
PARTNER_MEETINGS_REVISION = "c4e8a1d7f203"  # AD 설정 개편 리비전의 down_revision이다


def test_the_solution_text_revision_follows_the_forecast_snapshots() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert solution_free_text_revision() == SOLUTION_FREE_TEXT_REVISION
    assert solution_free_text_revision() != forecast_snapshots_revision()
    revision = script.get_revision(solution_free_text_revision())
    assert revision is not None
    assert revision.down_revision == forecast_snapshots_revision() == FORECAST_SNAPSHOTS_REVISION


def test_directory_service_account_revision_follows_partner_meetings_as_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    head = script.get_revision(directory_service_account_revision())
    assert script.get_heads() == [directory_service_account_revision()]
    assert directory_service_account_revision() != PARTNER_MEETINGS_REVISION
    assert head is not None
    assert head.down_revision == PARTNER_MEETINGS_REVISION
    assert head.path.endswith(f"20261029_{head.revision}_directory_service_account.py")


def test_the_partner_meetings_revision_follows_the_reports_layout_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    revision = script.get_revision(PARTNER_MEETINGS_REVISION)
    assert revision is not None
    assert revision.down_revision == REPORTS_LAYOUT_REVISION
    assert revision.path.endswith(f"20261028_{PARTNER_MEETINGS_REVISION}_partner_meetings.py")
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert PARTNER_MEETINGS_REVISION in history


def test_the_reports_layout_revision_follows_the_reports_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    layout = script.get_revision(REPORTS_LAYOUT_REVISION)
    assert layout is not None
    assert layout.down_revision == REPORTS_REVISION
    assert layout.path.endswith(f"20261028_{REPORTS_LAYOUT_REVISION}_reports_layout.py")
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert REPORTS_LAYOUT_REVISION in history


def test_the_reports_revision_follows_the_solution_text() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    head = script.get_revision(REPORTS_REVISION)
    assert head is not None
    assert head.down_revision == SOLUTION_FREE_TEXT_REVISION
    assert head.path.endswith(f"20261027_{REPORTS_REVISION}_reports.py")


def test_the_solution_free_text_revision_file_is_named_after_its_purpose() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    head = script.get_revision(solution_free_text_revision())

    assert head is not None
    assert head.path.endswith(f"20261022_{head.revision}_solution_free_text.py")


def test_the_forecast_snapshots_revision_follows_the_bigint_ids_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    head = script.get_revision(forecast_snapshots_revision())

    assert head is not None
    assert head.down_revision == bigint_ids_revision() == BIGINT_IDS_REVISION
    assert head.path.endswith(f"_{head.revision}_forecast_snapshots.py")
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert forecast_snapshots_revision() in history


def test_the_bigint_ids_revision_follows_the_users_required_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert bigint_ids_revision() != deals_users_required_revision()
    revision = script.get_revision(bigint_ids_revision())
    assert revision is not None
    assert revision.down_revision == USERS_REQUIRED_REVISION == deals_users_required_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert bigint_ids_revision() in history


def test_the_bigint_ids_revision_file_is_named_after_its_purpose() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    revision = script.get_revision(bigint_ids_revision())

    assert revision is not None
    assert revision.path.endswith(f"20261021_{revision.revision}_bigint_ids.py")


def test_the_users_required_revision_follows_the_next_action_status_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    revision = script.get_revision(deals_users_required_revision())

    assert revision is not None
    assert revision.down_revision == next_action_status_revision()
    assert deals_users_required_revision() != next_action_status_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert deals_users_required_revision() in history


def test_the_next_action_status_revision_follows_the_action_types_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    revision = script.get_revision(next_action_status_revision())

    assert next_action_status_revision() != action_types_revision()
    assert revision is not None
    assert revision.down_revision == action_types_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert next_action_status_revision() in history


def test_the_action_types_revision_follows_the_vendor_solution_revision() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    revision = script.get_revision(action_types_revision())

    assert action_types_revision() != vendor_solution_revision()
    assert revision is not None
    assert revision.down_revision == vendor_solution_revision()


def test_the_vendor_solution_revision_follows_the_alert_settings_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert vendor_solution_revision() != alert_settings_revision()
    revision = script.get_revision(vendor_solution_revision())
    assert revision is not None
    assert revision.down_revision == alert_settings_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert vendor_solution_revision() in history


def test_the_alert_settings_revision_follows_the_attachments_revision_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert alert_settings_revision() != attachments_revision()
    revision = script.get_revision(alert_settings_revision())
    assert revision is not None
    assert revision.down_revision == attachments_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert alert_settings_revision() in history


def test_the_attachments_revision_follows_the_action_snapshot_revision_in_the_head_history() -> (
    None
):
    script = ScriptDirectory.from_config(_alembic_config())

    assert attachments_revision() != action_snapshot_revision()
    revision = script.get_revision(attachments_revision())
    assert revision is not None
    assert revision.down_revision == action_snapshot_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert attachments_revision() in history


def test_the_action_snapshot_revision_follows_the_deal_model_revision_in_the_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    snapshot = script.get_revision(action_snapshot_revision())

    assert snapshot is not None
    assert action_snapshot_revision() != deal_model_revision()
    assert snapshot.down_revision == deal_model_revision()
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert action_snapshot_revision() in history


def test_the_deal_model_revision_follows_the_contacts_revision_and_is_in_the_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    assert deal_model_revision() != CONTACTS_REVISION
    revision = script.get_revision(deal_model_revision())
    assert revision is not None
    assert revision.down_revision == CONTACTS_REVISION
    history = {r.revision for r in script.iterate_revisions(script.get_heads()[0], "base")}
    assert deal_model_revision() in history


def test_the_contacts_revision_follows_the_codes_revision_and_is_in_the_single_head_history() -> (
    None
):
    script = ScriptDirectory.from_config(_alembic_config())
    contacts = script.get_revision(contacts_revision())

    assert contacts is not None
    assert contacts.revision == CONTACTS_REVISION
    assert contacts.down_revision == CODES_REVISION
    heads = script.get_heads()
    assert len(heads) == 1
    history = {r.revision for r in script.iterate_revisions(heads[0], "base")}
    assert CONTACTS_REVISION in history


def test_the_codes_revision_follows_the_user_fk_revision_and_is_in_the_single_head_history() -> (
    None
):
    script = ScriptDirectory.from_config(_alembic_config())
    codes = script.get_revision(CODES_REVISION)

    assert codes is not None
    assert codes.down_revision == USER_FK_REVISION
    heads = script.get_heads()
    assert len(heads) == 1
    history = {r.revision for r in script.iterate_revisions(heads[0], "base")}
    assert CODES_REVISION in history


def test_the_user_fk_revision_follows_the_legacy_head_and_is_in_the_single_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    heads = script.get_heads()

    assert len(heads) == 1
    user_fk = script.get_revision(USER_FK_REVISION)
    assert user_fk is not None
    assert user_fk.down_revision == LEGACY_HEAD
    history = {r.revision for r in script.iterate_revisions(heads[0], "base")}
    assert USER_FK_REVISION in history


def test_the_drop_revision_follows_the_previous_head_and_stays_in_the_single_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())

    heads = script.get_heads()

    assert len(heads) == 1
    drop = script.get_revision(DROP_DELETED_AT_REVISION)
    assert drop is not None
    assert drop.down_revision == DROP_PREVIOUS_HEAD
    history = {r.revision for r in script.iterate_revisions(heads[0], "base")}
    assert DROP_DELETED_AT_REVISION in history


def test_owner_revision_follows_the_stage_revision_and_is_in_the_single_head_history() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    owner = script.get_revision(OWNER_REVISION)

    assert owner is not None
    assert owner.down_revision == STAGE_REVISION
    heads = script.get_heads()
    assert len(heads) == 1
    history = {revision.revision for revision in script.iterate_revisions(heads[0], "base")}
    assert OWNER_REVISION in history


def test_history_revision_follows_the_previous_head_and_is_an_ancestor_of_the_single_head() -> None:
    script = ScriptDirectory.from_config(_alembic_config())
    revision = script.get_revision(HISTORY_REVISION)

    assert revision is not None
    assert revision.down_revision == AUTH_REVISION
    assert len(script.get_heads()) == 1
    ancestors = {r.revision for r in script.walk_revisions(base="base", head="heads")}
    assert revision.revision in ancestors
