"""User.change_profile·record_password_login·ensure_profile_editable.

PATCH 의미: 보내지 않은 값(UNSET)은 그대로 두고, None은 비운다. local에서 이름은 비울 수 없다.
"""

from datetime import timedelta

import pytest

from app.domain.auth.mode import AuthMode
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.profile import UNSET, ProfileChanges, ensure_profile_editable
from tests.factories import NOW, later
from tests.factories_auth import make_resigned_user, make_user


def test_profile_changes_default_to_unset_for_every_field() -> None:
    """변경 값을 주지 않은 칸은 모두 UNSET이다"""
    # when: 빈 변경 값을 만든다
    changes = ProfileChanges()

    # then: 모든 칸이 UNSET이다
    assert changes.display_name is UNSET
    assert changes.email is UNSET
    assert changes.phone is UNSET


def test_change_profile_updates_only_the_given_fields_and_touches_the_row() -> None:
    """보낸 칸만 바뀌고 수정 시각이 갱신된다

    테스트 코드: US-041
    """
    # given: 프로필이 모두 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")

    # when: 이름만 고친다
    changed = user.change_profile(
        ProfileChanges(display_name=" 이영업 "), later(60), require_name=True
    )

    # then: 이름만 바뀌고 수정 시각이 갱신된다
    assert changed is True
    assert (user.display_name, user.email, user.phone) == (
        "이영업",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert user.updated_at == later(60)


def test_change_profile_normalizes_email_and_phone() -> None:
    """이메일은 소문자로, 전화는 앞뒤 공백을 지워 저장한다

    테스트 코드: US-040
    """
    # given: 이름이 있는 kim
    user = make_user("kim", display_name="김영업")

    # when: 공백·대문자가 섞인 이메일과 전화로 고친다
    user.change_profile(
        ProfileChanges(email=" New@Corp.TEST ", phone=" +82 10-1111-2222 "),
        later(1),
        require_name=True,
    )

    # then: 정규화된 값이다
    assert (user.email, user.phone) == ("new@corp.test", "+82 10-1111-2222")


def test_change_profile_clears_email_with_none() -> None:
    """None을 보내면 그 칸이 비워진다

    테스트 코드: US-041
    """
    # given: 이메일이 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    # when: 이메일을 None으로 고친다
    changed = user.change_profile(ProfileChanges(email=None), later(1), require_name=True)

    # then: 바뀌었다는 결과이고 이메일이 None이다
    assert changed is True
    assert user.email is None


def test_change_profile_clears_phone_with_a_blank_string() -> None:
    """빈 문자열을 보내면 그 칸이 비워진다

    테스트 코드: US-041
    """
    # given: 전화가 있는 kim
    user = make_user("kim", display_name="김영업", phone="010-1234-5678")

    # when: 전화를 공백으로 고친다
    user.change_profile(ProfileChanges(phone="  "), later(1), require_name=True)

    # then: 전화가 None이다
    assert user.phone is None


def test_change_profile_without_changes_returns_false_and_leaves_updated_at() -> None:
    """바뀐 값이 없으면 false이고 수정 시각이 그대로다

    테스트 코드: US-042
    """
    # given: 프로필이 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")

    # when: 아무 칸도 주지 않고 고친다
    actual = user.change_profile(ProfileChanges(), later(60), require_name=True)
    # then: false이고 수정 시각이 그대로다
    assert actual is False
    assert user.updated_at == NOW


def test_change_profile_with_equal_values_returns_false() -> None:
    """정규화하면 같은 값이면 바뀐 것이 아니다

    테스트 코드: US-042
    """
    # given: 이름·이메일이 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    # when: 공백·대소문자만 다른 같은 값으로 고친다
    changed = user.change_profile(
        ProfileChanges(display_name=" 김영업 ", email="KIM@corp.test"), later(60), require_name=True
    )

    # then: false이고 수정 시각이 그대로다
    assert changed is False
    assert user.updated_at == NOW


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_change_profile_blank_name_when_required_is_rejected(blank: str | None) -> None:
    """이름이 필수일 때 비우면 거절되고 이름은 그대로다

    테스트 코드: US-043
    """
    # given: 이름이 있는 kim
    user = make_user("kim", display_name="김영업")

    # when: 이름을 비워서 고친다
    with pytest.raises(InvalidValueError):
        user.change_profile(ProfileChanges(display_name=blank), later(1), require_name=True)
    # then: 입력 오류이고 이름이 그대로다
    assert user.display_name == "김영업"


def test_change_profile_blank_name_when_not_required_clears_it() -> None:
    """이름이 필수가 아니면 비울 수 있다"""
    # given: 이름이 있는 kim
    user = make_user("kim", display_name="김영업")

    # when: 이름을 None으로 고친다
    user.change_profile(ProfileChanges(display_name=None), later(1), require_name=False)

    # then: 이름이 None이다
    assert user.display_name is None


@pytest.mark.parametrize(
    "changes",
    [
        ProfileChanges(email="abc"),
        ProfileChanges(phone="12"),
        ProfileChanges(display_name="가" * 201),
        ProfileChanges(display_name="a\x00b"),
    ],
)
def test_change_profile_invalid_value_is_rejected_and_nothing_changes(
    changes: ProfileChanges,
) -> None:
    """잘못된 값이 하나라도 있으면 거절되고 아무 칸도 바뀌지 않는다

    테스트 코드: US-044
    """
    # given: 이름·이메일이 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    # when: 잘못된 값으로 고친다
    with pytest.raises(InvalidValueError):
        user.change_profile(changes, later(1), require_name=True)
    # then: 입력 오류이고 이름·이메일·수정 시각이 그대로다
    assert (user.display_name, user.email, user.updated_at) == ("김영업", "kim@corp.test", NOW)


def test_change_profile_on_resigned_user_is_invalid_state() -> None:
    """퇴사자의 프로필은 고칠 수 없다

    테스트 코드: US-046
    """
    # given: 퇴사한 kim
    user = make_resigned_user("kim", display_name="김영업")

    # when: 전화를 고친다
    with pytest.raises(InvalidStateError):
        user.change_profile(ProfileChanges(phone="010-1234-5678"), later(10), require_name=True)
    # then: 상태 오류다


def test_change_profile_on_resigned_user_without_changes_is_still_invalid_state() -> None:
    """퇴사자는 바뀐 값이 없어도 상태 오류다

    테스트 코드: US-046
    """
    # given: 퇴사한 kim
    user = make_resigned_user("kim")

    # when: 아무 칸도 주지 않고 고친다
    with pytest.raises(InvalidStateError):
        user.change_profile(ProfileChanges(), later(10), require_name=True)
    # then: 상태 오류다


def test_record_password_login_sets_last_login_and_keeps_the_profile() -> None:
    """비밀번호 로그인을 기록하면 마지막 로그인 시각만 바뀌고 프로필은 그대로다."""
    # given: 이름과 이메일이 있는 kim
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    # when: 비밀번호 로그인을 기록한다
    user.record_password_login(later(30))

    # then: 마지막 로그인·수정 시각이 갱신되고 이름·이메일은 그대로다
    assert user.last_login_at == later(30)
    assert (user.display_name, user.email) == ("김영업", "kim@corp.test")
    assert user.updated_at == later(30)


def test_record_password_login_on_resigned_user_is_invalid_state() -> None:
    """퇴사한 사용자의 로그인 기록은 상태 오류다."""
    # given: 퇴사한 kim
    user = make_resigned_user("kim")

    # when·then: 비밀번호 로그인을 기록한다 → 상태 오류다
    with pytest.raises(InvalidStateError):
        user.record_password_login(NOW + timedelta(days=2))


def test_profile_name_or_email_edit_in_ad_mode_is_invalid_state() -> None:
    """AD 모드에서 이름·이메일 수정은 상태 오류다

    테스트 코드: US-045
    """
    # given: AD 모드
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(display_name="새 이름"), AuthMode.AD)
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(email="a@b.co"), AuthMode.AD)
    # when·then: 이름, 이메일, 이메일 비우기를 각각 확인한다 → 세 경우 모두 상태 오류다
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(email=None), AuthMode.AD)


def test_phone_edit_in_ad_mode_is_allowed() -> None:
    """AD 모드에서도 전화 수정·비움·변경 없음은 허용된다

    테스트 코드: US-045
    """
    # given: AD 모드
    ensure_profile_editable(ProfileChanges(phone="010-1234-5678"), AuthMode.AD)
    ensure_profile_editable(ProfileChanges(phone=None), AuthMode.AD)
    # when·then: 전화 수정 가능 여부를 확인한다 → 세 경우 모두 예외 없이 통과한다
    ensure_profile_editable(ProfileChanges(), AuthMode.AD)


def test_every_field_is_editable_in_local_mode() -> None:
    """local 모드에서는 이름·이메일·전화를 모두 고칠 수 있다

    테스트 코드: US-040
    """
    # when: 세 칸을 모두 고치는 변경을 확인한다 (전제: local 모드)
    ensure_profile_editable(
        ProfileChanges(display_name="새 이름", email="a@b.co", phone="010-1234-5678"),
        AuthMode.LOCAL,
    )
    # then: 예외 없이 통과한다
