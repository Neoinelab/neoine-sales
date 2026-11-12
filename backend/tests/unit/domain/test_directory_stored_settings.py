"""StoredDirectorySettings와 충돌 오류(DS-6·7). 저장 행에는 암호문과 자동 탐색한 Base DN이 있다."""

import dataclasses

import pytest

from app.domain.common.errors import DomainError, InvalidStateError, InvalidValueError
from app.domain.common.secret import SealedSecret
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
    """저장된 설정은 revision과 저장 시각·저장자를 가진다."""
    # when: 저장 설정을 만든다
    stored = _stored()

    # then: 값이 그대로 있다
    assert (stored.revision, stored.updated_at, stored.updated_by) == (1, NOW, None)
    assert stored.base_dn == BASE_DN
    assert stored.sealed_bind_password == SEALED


def test_stored_settings_keep_the_saving_users_id() -> None:
    """저장자 id를 그대로 가진다."""
    # when: 저장자를 지정해 만든다
    updated_by = _stored(revision=2, updated_by=uid("admin")).updated_by
    # then: 저장자 id가 같다
    assert updated_by == uid("admin")


def test_stored_settings_are_frozen() -> None:
    """저장된 설정은 바꿀 수 없다."""
    # when: 필드를 바꾸려 한다
    stored = _stored(updated_by=uid("admin"))

    # then: 오류가 난다
    with pytest.raises(dataclasses.FrozenInstanceError):
        stored.revision = 2  # type: ignore[misc]


def test_stored_settings_repr_hides_the_sealed_password() -> None:
    """repr에는 봉인된 비밀번호가 없다."""
    # when: repr을 만든다
    actual = repr(_stored())
    # then: 암호문이 보이지 않는다
    assert "sealed-dummy-token" not in actual


def test_stored_base_dn_length_limit_is_512() -> None:
    """저장되는 Base DN은 512자까지다."""
    # when: 512자와 513자로 만든다
    assert len(_stored(base_dn="dc=" + "x" * 509).base_dn) == 512
    with pytest.raises(InvalidValueError) as caught:
        _stored(base_dn="dc=" + "x" * 510)

    # then: 513자는 거절된다
    assert "base_dn" in str(caught.value)


@pytest.mark.parametrize("base_dn", ["", "dc=a\x00b", "dc=a\nb"])
def test_stored_base_dn_must_be_a_non_empty_text_without_control_characters(base_dn: str) -> None:
    """Base DN은 비어 있거나 제어문자가 있으면 거절된다."""
    # when: 빈 값·제어문자 Base DN으로 만든다
    with pytest.raises(InvalidValueError) as caught:
        _stored(base_dn=base_dn)

    # then: InvalidValueError다
    assert "base_dn" in str(caught.value)


def test_conflict_error_is_an_invalid_state_error_with_refresh_guidance() -> None:
    """revision 충돌은 새로고침을 안내하는 InvalidStateError다.

    테스트 코드: IN-024
    """
    # when: 충돌 오류를 만든다
    error = DirectorySettingsConflictError()

    # then: InvalidStateError이고 문구는 '설정이 다른 곳에서 바뀌었습니다...'다
    assert isinstance(error, InvalidStateError)
    assert isinstance(error, DomainError)
    assert "다른 곳에서 바뀌었습니다" in str(error)
