from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.auth.errors import AccessDeniedError, AuthenticationError
from app.domain.auth.principal import Principal, Role
from app.domain.auth.session import AuthSession, SessionId
from app.domain.common.errors import DomainError, InvalidStateError, InvalidValueError
from tests.factories import NOW, later


def _principal(**overrides: object) -> Principal:
    values: dict[str, object] = {
        "subject": "S-1-5-21-1",
        "email": "Kim@Neoine.Example",
        "name": " 김영업 ",
        "role": Role.SALES,
    }
    return Principal(**{**values, **overrides})  # type: ignore[arg-type]


def _session(**overrides: object) -> AuthSession:
    values: dict[str, object] = {
        "id": SessionId(uuid4()),
        "principal": _principal(),
        "created_at": NOW,
        "expires_at": NOW + timedelta(hours=8),
    }
    return AuthSession(**{**values, **overrides})  # type: ignore[arg-type]


class TestPrincipal:
    def test_normalizes_email_and_name(self) -> None:
        principal = _principal()

        assert principal.email == "kim@neoine.example"
        assert principal.name == "김영업"

    def test_email_is_optional_and_name_falls_back_to_subject(self) -> None:
        principal = _principal(email=None, name=" ")

        assert principal.email is None
        assert principal.name == "S-1-5-21-1"

    def test_subject_is_required(self) -> None:
        with pytest.raises(InvalidValueError):
            _principal(subject="  ")

    def test_roles_are_a_closed_set(self) -> None:
        assert {role.value for role in Role} == {"admin", "sales", "user"}


class TestAuthSession:
    def test_is_active_until_it_expires(self) -> None:
        session = _session()

        assert session.is_active(later(60))
        assert not session.is_active(NOW + timedelta(hours=8))

    def test_revoked_session_is_inactive_and_cannot_be_revoked_twice(self) -> None:
        session = _session()

        session.revoke(later(10))

        assert not session.is_active(later(20))
        assert session.revoked_at == later(10)
        with pytest.raises(InvalidStateError):
            session.revoke(later(30))

    def test_expiry_must_follow_creation(self) -> None:
        with pytest.raises(InvalidValueError):
            _session(expires_at=NOW)

    def test_times_require_a_timezone(self) -> None:
        with pytest.raises(InvalidValueError):
            _session(created_at=NOW.replace(tzinfo=None))


def test_auth_errors_are_domain_errors() -> None:
    assert issubclass(AuthenticationError, DomainError)
    assert issubclass(AccessDeniedError, DomainError)
