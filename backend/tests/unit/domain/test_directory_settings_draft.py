from dataclasses import fields

from app.domain.common.secret import SealedSecret
from app.domain.directory.settings import DirectorySettingsDraft
from tests.factories_directory import make_directory_connection


def test_draft_contains_a_proof_instead_of_credentials() -> None:
    token = SealedSecret("opaque-proof")
    draft = DirectorySettingsDraft(make_directory_connection(), token)
    assert {field.name for field in fields(draft)} == {"connection", "test_token"}
    assert draft.test_token is token
    assert "opaque-proof" not in repr(draft)
