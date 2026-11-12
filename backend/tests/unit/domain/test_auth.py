from datetime import timedelta

import pytest

from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import DomainError, InvalidStateError, InvalidValueError
from tests.factories import NOW, later
from tests.support.ids import new_id
from tests.support.user_ids import uid


def _principal(**overrides: object) -> Principal:
    values: dict[str, object] = {
        "user_id": uid("kim"),
        "subject": "S-1-5-21-1",
        "email": "Kim@Neoine.Example",
        "name": " 김영업 ",
        "role": Role.SALES,
    }
    return Principal(**{**values, **overrides})  # type: ignore[arg-type]


def _session(**overrides: object) -> AuthSession:
    values: dict[str, object] = {
        "id": SessionId(new_id()),
        "principal": _principal(),
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=8),
    }
    return AuthSession(**{**values, **overrides})  # type: ignore[arg-type]


class TestPrincipal:
    def test_normalizes_email_and_name(self) -> None:
        """Principal은 이메일과 이름을 정규화한다."""
        # when: 기본 값으로 Principal을 만든다
        principal = _principal()

        # then: 이메일과 이름이 정규화돼 있다
        assert principal.email == "kim@neoine.example"
        assert principal.name == "김영업"

    def test_email_is_optional_and_name_falls_back_to_subject(self) -> None:
        """이메일은 선택이고 이름이 공백이면 subject를 이름으로 쓴다."""
        # when: 이메일 없이 공백 이름으로 Principal을 만든다
        principal = _principal(email=None, name=" ")

        # then: 이메일은 None이고 이름은 subject다
        assert principal.email is None
        assert principal.name == "S-1-5-21-1"

    def test_subject_is_required(self) -> None:
        """subject가 공백이면 Principal을 만들 수 없다."""
        # when·then: 공백 subject로 만든다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            _principal(subject="  ")

    def test_principal_carries_the_user_id_of_the_users_row(self) -> None:
        """Principal은 users 행의 id를 가진다."""
        # when: Principal을 만든다
        user_id = _principal().user_id
        # then: user_id가 users 행의 id다
        assert user_id == uid("kim")

    def test_roles_are_a_closed_set(self) -> None:
        """역할은 admin·sales·user 세 값뿐이다."""
        # when: 역할 값을 모은다
        actual = {role.value for role in Role}
        # then: admin·sales·user 세 값뿐이다
        assert actual == {"admin", "sales", "user"}


class TestAuthSession:
    def test_is_active_until_it_expires(self) -> None:
        """세션은 만료 시각 직전까지 활성이고 만료 시각부터 비활성이다.

        테스트 코드: AU-053
        """
        # given: 발급 8시간 뒤 만료되는 세션
        session = _session()

        # when: 만료 전과 만료 시각의 활성 여부를 본다
        before_expiry = session.is_active(later(60))
        at_expiry = session.is_active(NOW + timedelta(hours=8))

        # then: 만료 전에는 활성, 만료 시각에는 비활성이다
        assert before_expiry
        assert not at_expiry

    def test_revoked_session_is_inactive_and_cannot_be_revoked_twice(self) -> None:
        """폐기한 세션은 비활성이고 다시 폐기할 수 없다.

        테스트 코드: AU-061
        """
        # given: 활성 세션
        session = _session()

        # when: 폐기한다
        session.revoke(later(10))

        # then: 비활성이고 두 번째 폐기는 오류다
        assert not session.is_active(later(20))
        assert session.revoked_at == later(10)
        with pytest.raises(InvalidStateError):
            session.revoke(later(30))

    def test_expiry_must_follow_creation(self) -> None:
        """만료 시각이 생성 시각 이후가 아니면 세션을 만들 수 없다."""
        # when·then: 만료 시각을 생성 시각과 같게 세션을 만든다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            _session(expires_at=NOW)

    def test_times_require_a_timezone(self) -> None:
        """시간대 없는 시각으로는 세션을 만들 수 없다."""
        # when·then: 시간대 없는 생성 시각으로 세션을 만든다 → 입력값 오류다
        with pytest.raises(InvalidValueError):
            _session(created_at=NOW.replace(tzinfo=None))


def test_auth_errors_are_domain_errors() -> None:
    """인증·접근 거부 오류는 도메인 오류의 하위 클래스다."""
    # when·then: 두 오류의 종류를 확인한다 → 둘 다 DomainError의 하위 클래스다
    assert issubclass(AuthenticationError, DomainError)
    assert issubclass(AccessDeniedError, DomainError)
