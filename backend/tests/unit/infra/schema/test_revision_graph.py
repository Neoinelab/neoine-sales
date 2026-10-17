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
    alert_settings_revision,
    attachments_revision,
    contacts_revision,
    deal_model_revision,
)


def test_the_alert_settings_revision_follows_the_attachments_revision_and_is_the_single_head() -> (
    None
):
    script = ScriptDirectory.from_config(_alembic_config())

    heads = script.get_heads()

    assert heads == [alert_settings_revision()]
    assert alert_settings_revision() != attachments_revision()
    head = script.get_revision(alert_settings_revision())
    assert head is not None
    assert head.down_revision == attachments_revision()


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
