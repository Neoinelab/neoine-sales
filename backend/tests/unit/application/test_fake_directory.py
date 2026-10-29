"""FakeDirectoryAuthenticator 자체의 동작(후속 유스케이스 테스트가 의존한다)."""

import pytest

from app.application.ports.directory import (
    DirectoryUnavailableError,
    InvalidCredentialsError,
    VerificationStage,
)
from app.domain.auth.credentials import LoginId, Password
from tests.factories_auth import BASE_DN
from tests.factories_directory import make_directory_settings
from tests.fakes.directory import FakeDirectoryAuthenticator


async def test_fake_records_calls_and_returns_registered_account() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1", display_name="김영업", email="kim@corp.test")
    settings = make_directory_settings()

    user = await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))

    assert user.display_name == "김영업"
    assert len(fake.authenticate_calls) == 1
    call = fake.authenticate_calls[0]
    assert (call.settings, call.base_dn, call.login_id, call.password) == (
        settings,
        BASE_DN,
        LoginId("kim"),
        "pw-1",
    )


async def test_fake_authenticate_failure_override_wins_over_account_lookup() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")
    fake.authenticate_fails_with = DirectoryUnavailableError(stage=VerificationStage.CONNECT)

    with pytest.raises(DirectoryUnavailableError):
        await fake.authenticate(
            make_directory_settings(), BASE_DN, LoginId("kim"), Password("pw-1")
        )

    assert len(fake.authenticate_calls) == 1  # 실패한 호출도 기록한다


async def test_fake_rejects_unknown_account_at_search_and_wrong_password_at_bind() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")

    for login, password, stage in (
        ("lee", "pw-1", VerificationStage.SEARCH),
        ("kim", "other", VerificationStage.BIND),
    ):
        with pytest.raises(InvalidCredentialsError) as caught:
            await fake.authenticate(
                make_directory_settings(), BASE_DN, LoginId(login), Password(password)
            )
        assert caught.value.stage is stage


async def test_fake_discover_returns_the_configured_base_dn_and_records_settings() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.base_dn = "dc=other,dc=test"
    settings = make_directory_settings()

    assert await fake.discover_base_dn(settings) == "dc=other,dc=test"
    fake.discover_fails_with = DirectoryUnavailableError(stage=VerificationStage.TLS)
    with pytest.raises(DirectoryUnavailableError):
        await fake.discover_base_dn(settings)

    assert fake.discover_calls == [settings, settings]


async def test_fake_fail_all_with_breaks_both_operations_and_none_restores_them() -> None:
    fake = FakeDirectoryAuthenticator()
    fake.add_account("kim", "pw-1")
    settings = make_directory_settings()
    fake.fail_all_with(DirectoryUnavailableError(stage=VerificationStage.CONNECT))

    with pytest.raises(DirectoryUnavailableError):
        await fake.discover_base_dn(settings)
    with pytest.raises(DirectoryUnavailableError):
        await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))
    fake.fail_all_with(None)

    assert await fake.discover_base_dn(settings) == BASE_DN
    assert (
        await fake.authenticate(settings, BASE_DN, LoginId("kim"), Password("pw-1"))
    ).login_id == "kim"
