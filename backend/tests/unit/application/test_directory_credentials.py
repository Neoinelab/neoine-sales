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
    """저장된 설정을 풀면 접속 정보와 평문 바인드 비밀번호를 돌려준다."""
    # given: 봉인된 비밀번호가 든 저장 설정
    cipher = FakeSecretCipher()
    stored = _stored(cipher)

    # when: 설정을 푼다
    settings = unseal_settings(cipher, stored)

    # then: 접속 정보와 평문 비밀번호가 나온다
    assert settings.connection == stored.connection
    assert settings.bind_password.reveal() == BIND_PASSWORD


def test_unseal_settings_failure_raises_unavailable_and_logs_a_warning_without_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """풀 수 없으면 오류를 내고 값 없는 경고 로그만 남긴다.

    테스트 코드: IN-034
    """
    # given: 풀 수 없는 암호문이 든 저장 설정
    cipher = FakeSecretCipher()
    stored = _stored(cipher, readable=False)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(DirectoryCredentialUnreadableError) as caught:
        unseal_settings(cipher, stored)

    assert isinstance(caught.value, DirectoryUnavailableError)
    # when: 설정을 푼다
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    # then: 복호화 실패 오류가 나고 로그에는 비밀번호·암호문 없이 경고만 있다
    assert any(
        "AD 바인드 비밀번호를 복호화하지 못했습니다(암호화 키 변경 여부 확인)" in r.getMessage()
        for r in warnings
    )
    assert stored.sealed_bind_password.token not in caplog.text
    assert stored.sealed_bind_password.token not in f"{caught.value!s}{caught.value!r}"


def test_try_unseal_returns_the_password_or_none() -> None:
    """풀 수 있으면 비밀번호를, 없으면 None을 돌려준다."""
    # given: 읽을 수 있는 암호문과 없는 설정
    cipher = FakeSecretCipher()

    readable = try_unseal(cipher, _stored(cipher))
    # when: 비밀번호 풀기를 시도한다
    unreadable = try_unseal(cipher, _stored(cipher, readable=False))

    # then: 비밀번호 또는 None이다
    assert readable is not None
    assert readable.reveal() == BIND_PASSWORD
    assert unreadable is None


def test_resolve_draft_uses_the_new_password_without_stored_settings() -> None:
    """저장된 설정이 없어도 새 비밀번호가 있으면 그 값을 쓴다."""
    # given: 저장된 설정이 없다
    cipher = FakeSecretCipher()
    draft = DirectorySettingsDraft(make_directory_connection(), Password("New-pw-2!"))

    # when: 새 비밀번호가 든 초안을 완성한다
    settings = resolve_draft(draft, None, cipher)

    # then: 새 비밀번호가 쓰인다
    assert settings.bind_password.reveal() == "New-pw-2!"


def test_resolve_draft_keeps_the_stored_password_when_endpoint_and_account_are_unchanged() -> None:
    """엔드포인트·계정이 같으면 비밀번호 생략은 저장된 값을 쓴다."""
    # given: 저장된 설정
    cipher = FakeSecretCipher()
    draft = DirectorySettingsDraft(
        make_directory_connection(user_filter="(uid={login_id})"), bind_password=None
    )

    # when: 같은 엔드포인트로 비밀번호 없는 초안을 완성한다
    settings = resolve_draft(draft, _stored(cipher), cipher)

    # then: 저장된 비밀번호가 쓰인다
    assert settings.bind_password.reveal() == BIND_PASSWORD


@pytest.mark.parametrize("readable", [True, False])
def test_resolve_draft_rejects_a_missing_password_when_it_cannot_be_reused(
    readable: bool,
) -> None:
    """저장 값을 쓸 수 없는 경우 비밀번호 생략은 거절된다."""
    # given: 저장 설정이 없거나 엔드포인트가 다르다
    cipher = FakeSecretCipher()
    other_host = make_directory_connection(host="dc9.corp.test")
    draft = DirectorySettingsDraft(other_host if readable else make_directory_connection(), None)

    # when·then: 비밀번호 없는 초안을 완성한다 → InvalidValueError다
    with pytest.raises(InvalidValueError) as caught:
        resolve_draft(draft, _stored(cipher, readable=readable), cipher)

    assert "bind_password" in str(caught.value)
