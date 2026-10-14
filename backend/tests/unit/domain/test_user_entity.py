"""T-D6~D10: User 엔티티(AUTH-2·10). 퇴사 처리와 삭제 정책은 test_user_resign / test_user_policy."""

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Permission, Role
from app.domain.common.contact import EMAIL_MAX_LENGTH
from tests.factories import NOW, later
from tests.factories_auth import make_user
from tests.support.user_ids import uid


def test_register_normalizes_login_id_and_starts_without_login_history() -> None:
    admin_id = uid("admin1")
    user = make_user(" Kim ", Role.USER, created_by_user_id=admin_id, now=NOW)

    assert user.login_id == LoginId("kim")
    assert user.role is Role.USER
    assert user.created_by_user_id == admin_id
    assert user.deleted_at is None
    assert user.delete_reason is None
    assert user.is_active
    assert user.created_at == NOW
    assert user.updated_at == NOW
    assert user.last_login_at is None
    assert user.display_name is None
    assert user.email is None


def test_register_generates_distinct_ids() -> None:
    assert make_user("a").id != make_user("a").id


def test_record_login_sets_last_login_and_profile() -> None:
    user = make_user()

    user.record_login(later(30), display_name="김영업", email="kim@corp.test")

    assert user.last_login_at == later(30)
    assert user.display_name == "김영업"
    assert user.email == "kim@corp.test"
    assert user.updated_at == later(30)


def test_record_login_overwrites_previous_profile_with_directory_values() -> None:
    user = make_user()
    user.record_login(later(10), display_name="옛 이름", email="old@corp.test")

    user.record_login(later(20), display_name="새 이름", email="new@corp.test")

    assert (user.display_name, user.email, user.last_login_at) == (
        "새 이름",
        "new@corp.test",
        later(20),
    )


AD_DISPLAY_NAME_LIMIT = 256  # AD displayName 스키마 상한
DOMAIN_NAME_LIMIT = 200
LONG_MAIL_LENGTH = 300


def test_record_login_accepts_an_ad_display_name_at_the_schema_limit() -> None:
    user = make_user()
    long_name = "가" * AD_DISPLAY_NAME_LIMIT

    user.record_login(later(10), display_name=long_name, email=None)

    assert user.last_login_at == later(10)
    assert user.display_name is None or (
        len(user.display_name) <= DOMAIN_NAME_LIMIT and long_name.startswith(user.display_name)
    )


def test_record_login_keeps_a_display_name_exactly_at_the_domain_limit() -> None:
    user = make_user()

    user.record_login(later(10), display_name="나" * DOMAIN_NAME_LIMIT, email=None)

    assert user.display_name == "나" * DOMAIN_NAME_LIMIT


def test_record_login_does_not_fail_on_an_overlong_mail_from_the_directory() -> None:
    user = make_user()
    long_mail = "a" * (LONG_MAIL_LENGTH - len("@corp.test")) + "@corp.test"

    user.record_login(later(10), display_name="김영업", email=long_mail)

    assert user.last_login_at == later(10)
    assert user.email is None or len(user.email) <= EMAIL_MAX_LENGTH


def test_to_principal_carries_user_id_login_id_as_subject_and_role() -> None:
    user = make_user("kim", Role.ADMIN)
    user.record_login(later(1), display_name="김영업", email="kim@corp.test")

    principal = user.to_principal()

    assert principal.user_id == user.id
    assert principal.subject == "kim"
    assert principal.name == "김영업"
    assert principal.email == "kim@corp.test"
    assert principal.role is Role.ADMIN
    assert principal.can(Permission.ADMINISTER)


def test_to_principal_falls_back_to_login_id_when_name_is_unknown() -> None:
    principal = make_user("kim").to_principal()

    assert principal.name == "kim"
    assert principal.email is None
