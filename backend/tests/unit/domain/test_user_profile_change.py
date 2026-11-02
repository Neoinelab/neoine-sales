"""User.change_profile·record_password_login·ensure_profile_editable (AC-5·8·10).

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
    changes = ProfileChanges()

    assert changes.display_name is UNSET
    assert changes.email is UNSET
    assert changes.phone is UNSET


def test_change_profile_updates_only_the_given_fields_and_touches_the_row() -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")

    changed = user.change_profile(
        ProfileChanges(display_name=" 이영업 "), later(60), require_name=True
    )

    assert changed is True
    assert (user.display_name, user.email, user.phone) == (
        "이영업",
        "kim@corp.test",
        "010-1234-5678",
    )
    assert user.updated_at == later(60)


def test_change_profile_normalizes_email_and_phone() -> None:
    user = make_user("kim", display_name="김영업")

    user.change_profile(
        ProfileChanges(email=" New@Corp.TEST ", phone=" +82 10-1111-2222 "),
        later(1),
        require_name=True,
    )

    assert (user.email, user.phone) == ("new@corp.test", "+82 10-1111-2222")


def test_change_profile_clears_email_with_none() -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    changed = user.change_profile(ProfileChanges(email=None), later(1), require_name=True)

    assert changed is True
    assert user.email is None


def test_change_profile_clears_phone_with_a_blank_string() -> None:
    user = make_user("kim", display_name="김영업", phone="010-1234-5678")

    user.change_profile(ProfileChanges(phone="  "), later(1), require_name=True)

    assert user.phone is None


def test_change_profile_without_changes_returns_false_and_leaves_updated_at() -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test", phone="010-1234-5678")

    assert user.change_profile(ProfileChanges(), later(60), require_name=True) is False
    assert user.updated_at == NOW


def test_change_profile_with_equal_values_returns_false() -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    changed = user.change_profile(
        ProfileChanges(display_name=" 김영업 ", email="KIM@corp.test"), later(60), require_name=True
    )

    assert changed is False
    assert user.updated_at == NOW


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_change_profile_blank_name_when_required_is_rejected(blank: str | None) -> None:
    user = make_user("kim", display_name="김영업")

    with pytest.raises(InvalidValueError):
        user.change_profile(ProfileChanges(display_name=blank), later(1), require_name=True)
    assert user.display_name == "김영업"


def test_change_profile_blank_name_when_not_required_clears_it() -> None:
    user = make_user("kim", display_name="김영업")

    user.change_profile(ProfileChanges(display_name=None), later(1), require_name=False)

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
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    with pytest.raises(InvalidValueError):
        user.change_profile(changes, later(1), require_name=True)
    assert (user.display_name, user.email, user.updated_at) == ("김영업", "kim@corp.test", NOW)


def test_change_profile_on_resigned_user_is_invalid_state() -> None:
    user = make_resigned_user("kim", display_name="김영업")

    with pytest.raises(InvalidStateError):
        user.change_profile(ProfileChanges(phone="010-1234-5678"), later(10), require_name=True)


def test_change_profile_on_resigned_user_without_changes_is_still_invalid_state() -> None:
    user = make_resigned_user("kim")

    with pytest.raises(InvalidStateError):
        user.change_profile(ProfileChanges(), later(10), require_name=True)


def test_record_password_login_sets_last_login_and_keeps_the_profile() -> None:
    user = make_user("kim", display_name="김영업", email="kim@corp.test")

    user.record_password_login(later(30))

    assert user.last_login_at == later(30)
    assert (user.display_name, user.email) == ("김영업", "kim@corp.test")
    assert user.updated_at == later(30)


def test_record_password_login_on_resigned_user_is_invalid_state() -> None:
    user = make_resigned_user("kim")

    with pytest.raises(InvalidStateError):
        user.record_password_login(NOW + timedelta(days=2))


def test_profile_name_or_email_edit_in_ad_mode_is_invalid_state() -> None:
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(display_name="새 이름"), AuthMode.AD)
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(email="a@b.co"), AuthMode.AD)
    with pytest.raises(InvalidStateError):
        ensure_profile_editable(ProfileChanges(email=None), AuthMode.AD)


def test_phone_edit_in_ad_mode_is_allowed() -> None:
    ensure_profile_editable(ProfileChanges(phone="010-1234-5678"), AuthMode.AD)
    ensure_profile_editable(ProfileChanges(phone=None), AuthMode.AD)
    ensure_profile_editable(ProfileChanges(), AuthMode.AD)


def test_every_field_is_editable_in_local_mode() -> None:
    ensure_profile_editable(
        ProfileChanges(display_name="새 이름", email="a@b.co", phone="010-1234-5678"),
        AuthMode.LOCAL,
    )
