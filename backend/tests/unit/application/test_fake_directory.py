"""FakeDirectoryAuthenticator 자체의 동작(후속 유스케이스 테스트가 의존한다)."""

import pytest

from app.application.ports.directory import (
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from tests.factories_auth import make_directory_settings
from tests.fakes.directory import FakeDirectoryAuthenticator


async def test_fake_records_calls_and_returns_registered_account() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1", display_name="김영업", email="kim@corp.test")
    settings = make_directory_settings()

    user = await fake.authenticate(settings, LoginId("kim"), Password("pw-1"))

    assert user.display_name == "김영업"
    assert len(fake.authenticate_calls) == 1
    call = fake.authenticate_calls[0]
    assert (call.settings, call.login_id, call.password) == (settings, LoginId("kim"), "pw-1")


async def test_fake_fail_with_overrides_account_lookup() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")
    fake.fail_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryUnavailableError):
        await fake.authenticate(make_directory_settings(), LoginId("kim"), Password("pw-1"))

    assert len(fake.authenticate_calls) == 1  # 실패한 호출도 기록한다


async def test_fake_rejects_unknown_account_and_wrong_password() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")

    for login, password in (("kim", "other"), ("lee", "pw-1")):
        with pytest.raises(InvalidCredentialsError):
            await fake.authenticate(make_directory_settings(), LoginId(login), Password(password))


async def test_fake_probe_records_settings_and_can_fail() -> None:
    fake = FakeDirectoryAuthenticator()
    settings = make_directory_settings()
    await fake.probe(settings)
    fake.probe_fails_with = DirectoryUnavailableError(stage=VerificationStage.TLS)

    with pytest.raises(DirectoryUnavailableError):
        await fake.probe(settings)

    assert fake.probe_calls == [settings, settings]
