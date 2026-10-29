"""DirectoryConnection·DirectorySettings 검증(2026-10-29 개편: 서비스 계정 search-then-bind).

위반 메시지에는 영문 필드 이름이 들어간다(web이 422 본문에 그대로 싣는다). 비밀번호는 repr에
나오지 않는다.
"""

import dataclasses

import pytest
from app.domain.common.secret import SealedSecret

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import (
    DEFAULT_PORTS,
    DISPLAY_NAME_ATTRIBUTE,
    EMAIL_ATTRIBUTE,
    RECEIVE_TIMEOUT_SECONDS,
    DirectoryConnection,
    DirectorySettings,
    SecurityMode,
    bind_password_of,
)
from tests.factories_auth import BIND_ACCOUNT, BIND_PASSWORD
from tests.factories_directory import make_directory_connection, make_directory_settings


def _bad(field: str, **overrides: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        make_directory_connection(**overrides)
    assert field in str(caught.value)


def test_security_modes_have_the_documented_values_and_default_ports() -> None:
    assert [mode.value for mode in SecurityMode] == ["none", "ssl", "starttls"]
    assert dict(DEFAULT_PORTS) == {
        SecurityMode.NONE: 389,
        SecurityMode.SSL: 636,
        SecurityMode.STARTTLS: 389,
    }


def test_fixed_values_replace_the_removed_inputs() -> None:
    assert RECEIVE_TIMEOUT_SECONDS == 10
    assert DISPLAY_NAME_ATTRIBUTE == "displayName"
    assert EMAIL_ATTRIBUTE == "mail"


def test_valid_connection_keeps_normalized_host_and_default_timeout() -> None:
    connection = DirectoryConnection(
        host="DC1.Corp.Test",
        port=636,
        security=SecurityMode.SSL,
        bind_account=BIND_ACCOUNT,
        user_filter="(sAMAccountName={login_id})",
    )

    assert connection.host == "dc1.corp.test"
    assert connection.connect_timeout_seconds == 5


def test_connection_rejects_a_host_with_scheme_or_port_naming_the_field() -> None:
    _bad("host", host="ldaps://dc1.corp.test")
    _bad("host", host="dc1.corp.test:636")


def test_connection_is_frozen() -> None:
    connection = make_directory_connection()

    with pytest.raises(dataclasses.FrozenInstanceError):
        connection.port = 389  # type: ignore[misc]


@pytest.mark.parametrize(
    ("port", "ok"), [(0, False), (1, True), (65535, True), (65536, False), (-1, False)]
)
def test_port_outside_range_is_rejected_with_field_name(port: int, ok: bool) -> None:
    if ok:
        assert make_directory_connection(port=port).port == port
    else:
        _bad("port", port=port)


@pytest.mark.parametrize(
    ("value", "ok"), [(0, False), (1, True), (30, True), (31, False), (-1, False)]
)
def test_connect_timeout_outside_1_to_30_is_rejected(value: int, ok: bool) -> None:
    if ok:
        assert (
            make_directory_connection(connect_timeout_seconds=value).connect_timeout_seconds
            == value
        )
    else:
        _bad("connect_timeout_seconds", connect_timeout_seconds=value)


@pytest.mark.parametrize(
    "account",
    [
        "cn=svc,ou=services,dc=corp,dc=test",
        "svc-sales@corp.test",
        "CORP\\svc-sales",
        "svc-sales",
        "x" * 256,
    ],
)
def test_bind_account_accepts_dn_upn_and_domain_forms(account: str) -> None:
    assert make_directory_connection(bind_account=account).bind_account == account


@pytest.mark.parametrize("account", ["", "x" * 257, "svc\x01", "svc\n", "svc\x00", "svc\x7f"])
def test_bind_account_empty_too_long_or_control_char_is_rejected(account: str) -> None:
    _bad("bind_account", bind_account=account)


@pytest.mark.parametrize(
    "user_filter",
    [
        "uid=x",
        "(uid=x)",
        "(uid={login_id}",
        "uid={login_id})",
        "(uid={login_id}))",
        "((uid={login_id})",
        "(&(objectClass=user)(sAMAccountName={login_id})",
        "({login_id}={login_id})",
        "(uid={login_id}{login_id})",
        "(uid={login_id}{0})",
        "",
    ],
)
def test_user_filter_rules_are_kept(user_filter: str) -> None:
    _bad("user_filter", user_filter=user_filter)


@pytest.mark.parametrize(
    "user_filter",
    [
        "(uid={login_id})",
        "(&(objectClass=user)(sAMAccountName={login_id}))",
        "(|(uid={login_id})(mail=fixed@corp.test))",
    ],
)
def test_valid_filters_are_accepted(user_filter: str) -> None:
    assert make_directory_connection(user_filter=user_filter).user_filter == user_filter


def test_user_filter_length_limit_is_512() -> None:
    def filter_of_length(total: int) -> str:
        return "(cn={login_id}" + "x" * (total - len("(cn={login_id})")) + ")"

    assert len(make_directory_connection(user_filter=filter_of_length(512)).user_filter) == 512
    _bad("user_filter", user_filter=filter_of_length(513))


@pytest.mark.parametrize(
    "removed",
    [
        "server_urls",
        "use_starttls",
        "ca_cert_pem",
        "bind_template",
        "base_dn",
        "display_name_attribute",
        "email_attribute",
        "receive_timeout_seconds",
    ],
)
def test_removed_inputs_are_not_connection_fields(removed: str) -> None:
    assert removed not in {f.name for f in dataclasses.fields(DirectoryConnection)}
    with pytest.raises(TypeError):
        make_directory_connection(**{removed: "x"})


def test_same_endpoint_and_account_compares_host_port_security_and_account_only() -> None:
    base = make_directory_connection()

    assert base.same_endpoint_and_account(
        make_directory_connection(user_filter="(uid={login_id})", connect_timeout_seconds=9)
    )
    for change in (
        {"host": "dc2.corp.test"},
        {"port": 3269},
        {"security": SecurityMode.STARTTLS},
        {"bind_account": "cn=other,dc=corp,dc=test"},
    ):
        assert not base.same_endpoint_and_account(make_directory_connection(**change))


@pytest.mark.parametrize("raw", ["", "   ", "\t\n", "a\x00b", "a" * 257])
def test_bind_password_errors_name_the_field(raw: str) -> None:
    with pytest.raises(InvalidValueError) as caught:
        bind_password_of(raw)

    assert "bind_password" in str(caught.value)


def test_bind_password_of_accepts_the_longest_value_and_keeps_spaces() -> None:
    assert bind_password_of("a" * 256).reveal() == "a" * 256
    assert bind_password_of(" pw with spaces ").reveal() == " pw with spaces "


def test_settings_carry_connection_and_password() -> None:
    settings = make_directory_settings()

    assert settings.connection == make_directory_connection()
    assert settings.bind_password.reveal() == BIND_PASSWORD
    assert isinstance(settings, DirectorySettings)


def test_settings_repr_hides_bind_password() -> None:
    settings = DirectorySettings(
        connection=make_directory_connection(), bind_password=Password(BIND_PASSWORD)
    )

    assert BIND_PASSWORD not in repr(settings)
    assert BIND_PASSWORD not in str(settings)


def test_sealed_secret_repr_hides_the_token() -> None:
    sealed = SealedSecret("gAAAAA-token-value")

    assert "gAAAAA-token-value" not in repr(sealed)
    assert "gAAAAA-token-value" not in str(sealed)
    assert sealed.token == "gAAAAA-token-value"  # noqa: S105 - 가짜 값
