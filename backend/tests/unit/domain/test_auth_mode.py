"""인증 방식(AuthMode)과 유효 방식 판정 (AC-1·AC-14): 저장값 > admin이 이미 있으면 ad > 미선택."""

from datetime import UTC, datetime

import pytest

from app.domain.auth.mode import AuthMode, AuthSettings, effective_mode

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def test_auth_mode_values_are_ad_and_local() -> None:
    assert {m.value for m in AuthMode} == {"ad", "local"}
    assert AuthMode("local") is AuthMode.LOCAL


@pytest.mark.parametrize("mode", list(AuthMode))
def test_stored_mode_wins_over_every_other_signal(mode: AuthMode) -> None:
    stored = AuthSettings(mode=mode, updated_at=NOW)

    assert effective_mode(stored, has_admin=False) is mode
    assert effective_mode(stored, has_admin=True) is mode
    assert effective_mode(stored, has_admin=False, has_directory=True) is mode


def test_no_row_and_an_admin_means_ad_for_systems_set_up_before_the_mode_existed() -> None:
    assert effective_mode(None, has_admin=True) is AuthMode.AD


def test_no_row_and_a_saved_directory_means_ad() -> None:
    assert effective_mode(None, has_admin=False, has_directory=True) is AuthMode.AD


def test_no_row_no_admin_no_directory_means_not_chosen_yet() -> None:
    assert effective_mode(None, has_admin=False) is None
    assert effective_mode(None, has_admin=False, has_directory=False) is None


def test_auth_settings_are_immutable() -> None:
    stored = AuthSettings(mode=AuthMode.AD, updated_at=NOW)

    with pytest.raises(AttributeError):
        stored.mode = AuthMode.LOCAL  # type: ignore[misc]
