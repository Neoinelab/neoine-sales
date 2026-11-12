"""인증 방식(AuthMode)과 유효 방식 판정: 저장값 > admin이 이미 있으면 ad > 미선택."""

from datetime import UTC, datetime

import pytest

from app.domain.auth.mode import AuthMode, AuthSettings, effective_mode

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def test_auth_mode_values_are_ad_and_local() -> None:
    """인증 방식 값은 ad와 local 두 가지뿐이다."""
    # when·then: 열거형의 값 집합과 문자열 변환을 확인한다
    assert {m.value for m in AuthMode} == {"ad", "local"}
    assert AuthMode("local") is AuthMode.LOCAL


@pytest.mark.parametrize("mode", list(AuthMode))
def test_stored_mode_wins_over_every_other_signal(mode: AuthMode) -> None:
    """저장된 인증 방식이 있으면 admin·디렉터리 유무와 상관없이 그 방식이 유효하다."""
    # given: 방식이 저장된 설정
    stored = AuthSettings(mode=mode, updated_at=NOW)

    # when: admin·디렉터리 유무를 바꿔 가며 유효 방식을 판정한다
    without_admin = effective_mode(stored, has_admin=False)
    with_admin = effective_mode(stored, has_admin=True)
    with_directory = effective_mode(stored, has_admin=False, has_directory=True)

    # then: 모두 저장된 방식이다
    assert without_admin is mode
    assert with_admin is mode
    assert with_directory is mode


def test_no_row_and_an_admin_means_ad_for_systems_set_up_before_the_mode_existed() -> None:
    """저장값은 없고 admin이 있으면 방식이 생기기 전에 설정된 시스템이므로 ad로 본다."""
    # when: 저장값 없이 admin이 있는 상태로 판정한다
    mode = effective_mode(None, has_admin=True)

    # then: ad다
    assert mode is AuthMode.AD


def test_no_row_and_a_saved_directory_means_ad() -> None:
    """저장값은 없고 AD 설정이 저장돼 있으면 ad로 본다."""
    # when: 저장값 없이 디렉터리 설정만 있는 상태로 판정한다
    mode = effective_mode(None, has_admin=False, has_directory=True)

    # then: ad다
    assert mode is AuthMode.AD


def test_no_row_no_admin_no_directory_means_not_chosen_yet() -> None:
    """저장값·admin·디렉터리가 모두 없으면 아직 선택하지 않은 것이다."""
    # when: 아무 신호도 없는 상태로 판정한다
    default = effective_mode(None, has_admin=False)
    explicit = effective_mode(None, has_admin=False, has_directory=False)

    # then: 둘 다 미선택(None)이다
    assert default is None
    assert explicit is None


def test_auth_settings_are_immutable() -> None:
    """인증 설정 값은 만든 뒤 바꿀 수 없다."""
    # given: 저장된 설정
    stored = AuthSettings(mode=AuthMode.AD, updated_at=NOW)

    # when·then: 방식을 바꾸려 하면 AttributeError가 난다
    with pytest.raises(AttributeError):
        stored.mode = AuthMode.LOCAL  # type: ignore[misc]
