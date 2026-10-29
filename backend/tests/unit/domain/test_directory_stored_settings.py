"""StoredDirectorySettings와 충돌 오류(DS-6·7). 저장 행에는 암호문과 자동 탐색한 Base DN이 있다."""

import dataclasses

import pytest
from app.domain.common.secret import SealedSecret

from app.domain.common.errors import DomainError, InvalidStateError, InvalidValueError
from app.domain.directory.errors import DirectorySettingsConflictError
from app.domain.directory.settings import StoredDirectorySettings
from tests.factories import NOW
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_connection
from tests.support.user_ids import uid

SEALED = SealedSecret("sealed-dummy-token")


def _stored(**overrides: object) -> StoredDirectorySettings:
    values: dict[str, object] = {
        "connection": make_directory_connection(),
        "sealed_bind_password": SEALED,
        "base_dn": BASE_DN,
        "revision": 1,
        "updated_at": NOW,
        "updated_by": None,
    }
    return StoredDirectorySettings(**{**values, **overrides})  # type: ignore[arg-type]


def test_stored_settings_carry_revision_and_audit_fields() -> None:
    stored = _stored()

    assert (stored.revision, stored.updated_at, stored.updated_by) == (1, NOW, None)
    assert stored.base_dn == BASE_DN
    assert stored.sealed_bind_password == SEALED


def test_stored_settings_keep_the_saving_users_id() -> None:
    assert _stored(revision=2, updated_by=uid("admin")).updated_by == uid("admin")


def test_stored_settings_are_frozen() -> None:
    stored = _stored(updated_by=uid("admin"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        stored.revision = 2  # type: ignore[misc]


def test_stored_settings_repr_hides_the_sealed_password() -> None:
    assert "sealed-dummy-token" not in repr(_stored())


def test_stored_base_dn_length_limit_is_512() -> None:
    assert len(_stored(base_dn="dc=" + "x" * 509).base_dn) == 512
    with pytest.raises(InvalidValueError) as caught:
        _stored(base_dn="dc=" + "x" * 510)

    assert "base_dn" in str(caught.value)


@pytest.mark.parametrize("base_dn", ["", "dc=a\x00b", "dc=a\nb"])
def test_stored_base_dn_must_be_a_non_empty_text_without_control_characters(base_dn: str) -> None:
    with pytest.raises(InvalidValueError) as caught:
        _stored(base_dn=base_dn)

    assert "base_dn" in str(caught.value)


def test_conflict_error_is_an_invalid_state_error_with_refresh_guidance() -> None:
    error = DirectorySettingsConflictError()

    assert isinstance(error, InvalidStateError)
    assert isinstance(error, DomainError)
    assert "다른 곳에서 바뀌었습니다" in str(error)
