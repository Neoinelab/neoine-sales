"""User 엔티티(AUTH-2·10). 퇴사 처리와 삭제 정책은 test_user_resign / test_user_policy."""

from datetime import datetime

import pytest

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Permission, Role
from app.domain.common.contact import EMAIL_MAX_LENGTH
from app.domain.common.errors import InvalidStateError, InvalidValueError
from app.domain.user.value_objects import UserId
from tests.factories import NOW, later
from tests.factories_auth import make_resigned_user, make_user


def test_register_normalizes_login_id_and_starts_without_login_history() -> None:
    """등록한 사용자는 아이디가 정규화되고 로그인 이력 없이 시작한다."""
    # when: 공백이 든 아이디로 사용자를 등록한다
    user = make_user(" Kim ", Role.USER, now=NOW)

    # then: 아이디가 정규화되고 재직 상태이며 로그인 이력·프로필이 비어 있다
    assert user.login_id == LoginId("kim")
    assert user.role is Role.USER
    assert not hasattr(user, "created_by_user_id")
    assert user.deleted_at is None
    assert not hasattr(user, "delete_reason")
    assert user.is_active
    assert user.created_at == NOW
    assert user.updated_at == NOW
    assert user.last_login_at is None
    assert user.display_name is None
    assert user.email is None


def test_register_uses_the_given_id() -> None:
    """등록할 때 준 id를 그대로 쓴다."""
    # when: id를 지정해 등록한다
    user = make_user("a", entity_id=UserId(7))

    # then: 사용자 id가 지정한 값이다
    assert user.id == 7


def test_record_login_sets_last_login_and_profile() -> None:
    """로그인을 기록하면 마지막 로그인 시각과 프로필이 채워진다."""
    # given: 로그인 이력이 없는 사용자
    user = make_user()

    # when: 디렉터리 프로필과 함께 로그인을 기록한다
    user.record_login(later(30), display_name="김영업", email="kim@corp.test")

    # then: 마지막 로그인·이름·이메일·수정 시각이 갱신된다
    assert user.last_login_at == later(30)
    assert user.display_name == "김영업"
    assert user.email == "kim@corp.test"
    assert user.updated_at == later(30)


def test_record_login_overwrites_previous_profile_with_directory_values() -> None:
    """다시 로그인하면 이전 프로필을 디렉터리 값으로 덮어쓴다."""
    # given: 이전 프로필이 기록된 사용자
    user = make_user()
    user.record_login(later(10), display_name="옛 이름", email="old@corp.test")

    # when: 새 프로필로 다시 로그인을 기록한다
    user.record_login(later(20), display_name="새 이름", email="new@corp.test")

    # then: 이름·이메일·마지막 로그인이 새 값이다
    assert (user.display_name, user.email, user.last_login_at) == (
        "새 이름",
        "new@corp.test",
        later(20),
    )


def test_fallback_login_updates_last_login_only() -> None:
    """대체 로그인은 마지막 로그인 시각만 갱신한다."""
    # given: 프로필이 기록된 사용자
    user = make_user()
    user.record_login(later(10), display_name="김영업", email="kim@corp.test")

    # when: 대체 로그인을 기록한다
    user.record_fallback_login(later(30))

    # then: 시각만 갱신되고 프로필은 그대로다
    assert user.last_login_at == later(30)
    assert user.updated_at == later(30)
    assert (user.display_name, user.email) == ("김영업", "kim@corp.test")  # 디렉터리 값이 없다


def test_fallback_login_keeps_an_unknown_profile_unknown() -> None:
    """프로필을 모르는 사용자의 대체 로그인은 프로필을 비워 둔다."""
    # given: 프로필이 없는 사용자
    user = make_user()

    # when: 대체 로그인을 기록한다
    user.record_fallback_login(later(30))

    # then: 프로필은 없고 마지막 로그인만 기록된다
    assert (user.display_name, user.email, user.last_login_at) == (None, None, later(30))


def test_fallback_login_of_resigned_user_is_rejected() -> None:
    """퇴사한 사용자의 대체 로그인은 거부되고 상태가 바뀌지 않는다."""
    # given: 퇴사한 사용자
    user = make_resigned_user()
    before = (user.last_login_at, user.updated_at)

    # when·then: 대체 로그인을 기록하면 InvalidStateError가 난다
    with pytest.raises(InvalidStateError):
        user.record_fallback_login(later(9999))

    # then: 로그인 시각과 수정 시각이 그대로다
    assert (user.last_login_at, user.updated_at) == before


def test_fallback_login_needs_a_timezone_aware_time() -> None:
    """대체 로그인 시각은 시간대가 있어야 한다."""
    # given: 재직 사용자
    user = make_user()

    # when·then: 시간대 없는 시각으로 기록하면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        user.record_fallback_login(datetime(2026, 1, 2, 9, 0))


AD_DISPLAY_NAME_LIMIT = 256  # AD displayName 스키마 상한
DOMAIN_NAME_LIMIT = 200
LONG_MAIL_LENGTH = 300


def test_record_login_accepts_an_ad_display_name_at_the_schema_limit() -> None:
    """AD 스키마 상한(256자) 표시 이름으로도 로그인 기록이 실패하지 않는다."""
    # given: 256자 표시 이름
    user = make_user()
    long_name = "가" * AD_DISPLAY_NAME_LIMIT

    # when: 로그인을 기록한다
    user.record_login(later(10), display_name=long_name, email=None)

    # then: 로그인이 기록되고 이름은 도메인 상한 이내로 잘리거나 비어 있다
    assert user.last_login_at == later(10)
    assert user.display_name is None or (
        len(user.display_name) <= DOMAIN_NAME_LIMIT and long_name.startswith(user.display_name)
    )


def test_record_login_keeps_a_display_name_exactly_at_the_domain_limit() -> None:
    """도메인 상한(200자) 표시 이름은 그대로 보관한다."""
    # given: 재직 사용자
    user = make_user()

    # when: 200자 표시 이름으로 로그인을 기록한다
    user.record_login(later(10), display_name="나" * DOMAIN_NAME_LIMIT, email=None)

    # then: 이름이 그대로 보관된다
    assert user.display_name == "나" * DOMAIN_NAME_LIMIT


def test_record_login_does_not_fail_on_an_overlong_mail_from_the_directory() -> None:
    """디렉터리의 너무 긴 메일 주소로도 로그인 기록이 실패하지 않는다."""
    # given: 300자 메일 주소
    user = make_user()
    long_mail = "a" * (LONG_MAIL_LENGTH - len("@corp.test")) + "@corp.test"

    # when: 로그인을 기록한다
    user.record_login(later(10), display_name="김영업", email=long_mail)

    # then: 로그인이 기록되고 이메일은 상한 이내이거나 비어 있다
    assert user.last_login_at == later(10)
    assert user.email is None or len(user.email) <= EMAIL_MAX_LENGTH


def test_to_principal_carries_user_id_login_id_as_subject_and_role() -> None:
    """Principal은 사용자 id·아이디(subject)·이름·이메일·역할을 담는다."""
    # given: 프로필이 기록된 admin 사용자
    user = make_user("kim", Role.ADMIN)
    user.record_login(later(1), display_name="김영업", email="kim@corp.test")

    # when: Principal로 바꾼다
    principal = user.to_principal()

    # then: 사용자 정보와 관리 권한이 담긴다
    assert principal.user_id == user.id
    assert principal.subject == "kim"
    assert principal.name == "김영업"
    assert principal.email == "kim@corp.test"
    assert principal.role is Role.ADMIN
    assert principal.can(Permission.ADMINISTER)


def test_to_principal_falls_back_to_login_id_when_name_is_unknown() -> None:
    """이름을 모르면 Principal 이름은 로그인 아이디다."""
    # when: 이름이 없는 사용자를 Principal로 바꾼다
    principal = make_user("kim").to_principal()

    # then: 이름은 아이디이고 이메일은 없다
    assert principal.name == "kim"
    assert principal.email is None
