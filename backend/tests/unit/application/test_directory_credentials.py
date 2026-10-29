"""application/directory/credentials.py: 바인드 비밀번호 복호화와 후보 설정 완성(AC4·AC10)."""

import logging

import pytest
from app.application.directory.credentials import resolve_draft, try_unseal, unseal_settings

from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.directory import DirectoryUnavailableError
from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectorySettingsDraft, StoredDirectorySettings
from tests.factories import NOW
from tests.factories_auth import BASE_DN, BIND_PASSWORD
from tests.factories_directory import make_directory_connection
from tests.fakes.secret_cipher import FakeSecretCipher, foreign_secret


def _stored(cipher: FakeSecretCipher, *, readable: bool = True) -> StoredDirectorySettings:
    return StoredDirectorySettings(
        connection=make_directory_connection(),
        sealed_bind_password=cipher.seal(BIND_PASSWORD) if readable else foreign_secret(),
        base_dn=BASE_DN,
        revision=1,
        updated_at=NOW,
        updated_by=None,
    )


def test_unseal_settings_returns_the_connection_with_the_plain_password() -> None:
    cipher = FakeSecretCipher()
    stored = _stored(cipher)

    settings = unseal_settings(cipher, stored)

    assert settings.connection == stored.connection
    assert settings.bind_password.reveal() == BIND_PASSWORD


def test_unseal_settings_failure_raises_unavailable_and_logs_a_warning_without_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cipher = FakeSecretCipher()
    stored = _stored(cipher, readable=False)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(DirectoryCredentialUnreadableError) as caught:
        unseal_settings(cipher, stored)

    assert isinstance(caught.value, DirectoryUnavailableError)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any(
        "AD 바인드 비밀번호를 복호화하지 못했습니다(암호화 키 변경 여부 확인)" in r.getMessage()
        for r in warnings
    )
    assert stored.sealed_bind_password.token not in caplog.text
    assert stored.sealed_bind_password.token not in f"{caught.value!s}{caught.value!r}"


def test_try_unseal_returns_the_password_or_none() -> None:
    cipher = FakeSecretCipher()

    readable = try_unseal(cipher, _stored(cipher))
    unreadable = try_unseal(cipher, _stored(cipher, readable=False))

    assert readable is not None
    assert readable.reveal() == BIND_PASSWORD
    assert unreadable is None


def test_resolve_draft_uses_the_new_password_without_stored_settings() -> None:
    cipher = FakeSecretCipher()
    draft = DirectorySettingsDraft(make_directory_connection(), Password("New-pw-2!"))

    settings = resolve_draft(draft, None, cipher)

    assert settings.bind_password.reveal() == "New-pw-2!"


def test_resolve_draft_keeps_the_stored_password_when_endpoint_and_account_are_unchanged() -> None:
    cipher = FakeSecretCipher()
    draft = DirectorySettingsDraft(
        make_directory_connection(user_filter="(uid={login_id})"), bind_password=None
    )

    settings = resolve_draft(draft, _stored(cipher), cipher)

    assert settings.bind_password.reveal() == BIND_PASSWORD


@pytest.mark.parametrize("readable", [True, False])
def test_resolve_draft_rejects_a_missing_password_when_it_cannot_be_reused(
    readable: bool,
) -> None:
    cipher = FakeSecretCipher()
    other_host = make_directory_connection(host="dc9.corp.test")
    draft = DirectorySettingsDraft(other_host if readable else make_directory_connection(), None)

    with pytest.raises(InvalidValueError) as caught:
        resolve_draft(draft, _stored(cipher, readable=readable), cipher)

    assert "bind_password" in str(caught.value)
