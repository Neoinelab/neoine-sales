"""StoredDirectorySettings와 충돌 오류(DS-6·7)."""

import dataclasses

import pytest

from app.domain.common.errors import DomainError, InvalidStateError
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import StoredDirectorySettings
from tests.factories import NOW
from tests.factories_auth import make_directory_settings


def test_stored_settings_carry_revision_and_audit_fields() -> None:
    stored = StoredDirectorySettings(
        settings=make_directory_settings(), revision=1, updated_at=NOW, updated_by=None
    )

    assert (stored.revision, stored.updated_at, stored.updated_by) == (1, NOW, None)


def test_stored_settings_are_frozen() -> None:
    stored = StoredDirectorySettings(
        settings=make_directory_settings(), revision=1, updated_at=NOW, updated_by="admin"
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        stored.revision = 2  # type: ignore[misc]


def test_conflict_error_is_an_invalid_state_error_with_refresh_guidance() -> None:
    error = DirectorySettingsConflictError()

    assert isinstance(error, InvalidStateError)
    assert isinstance(error, DomainError)
    assert "다른 곳에서 바뀌었습니다" in str(error)
