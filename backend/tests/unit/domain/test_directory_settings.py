"""DirectoryConnection·DirectorySettings 검증(2026-10-29 개편: 서비스 계정 search-then-bind).

위반 메시지에는 영문 필드 이름이 들어간다(web이 422 본문에 그대로 싣는다). 비밀번호는 repr에
나오지 않는다.
"""

import dataclasses

import pytest

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.common.secret import SealedSecret
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
    """보안 연결 방식은 none·ssl·starttls이고 기본 포트는 389·636·389다."""
    # when: 방식과 기본 포트 표를 읽는다
    actual = [mode.value for mode in SecurityMode]
    # then: 문서와 같다
    assert actual == ["none", "ssl", "starttls"]
    assert dict(DEFAULT_PORTS) == {
        SecurityMode.NONE: 389,
        SecurityMode.SSL: 636,
        SecurityMode.STARTTLS: 389,
    }


def test_fixed_values_replace_the_removed_inputs() -> None:
    """수신 제한 시간·표시 이름·메일 속성은 입력이 아니라 고정 값이다."""
    # when·then: 고정 값을 읽는다 → 10초, displayName, mail이다
    assert RECEIVE_TIMEOUT_SECONDS == 10
    assert DISPLAY_NAME_ATTRIBUTE == "displayName"
    assert EMAIL_ATTRIBUTE == "mail"


def test_valid_connection_keeps_normalized_host_and_default_timeout() -> None:
    """연결 제한 시간을 생략하면 5초이고 호스트는 소문자로 정규화된다.

    테스트 코드: IN-019
    """
    # when: 연결 제한 시간 없이 접속 정보를 만든다
    connection = DirectoryConnection(
        host="DC1.Corp.Test",
        port=636,
        security=SecurityMode.SSL,
        bind_account=BIND_ACCOUNT,
        user_filter="(sAMAccountName={login_id})",
    )

    # then: 호스트는 소문자, 제한 시간은 5다
    assert connection.host == "dc1.corp.test"
    assert connection.connect_timeout_seconds == 5


def test_connection_rejects_a_host_with_scheme_or_port_naming_the_field() -> None:
    """scheme이나 포트가 붙은 호스트는 host 필드 이름이 든 오류다.

    테스트 코드: IN-017
    """
    _bad("host", host="ldaps://dc1.corp.test")
    # when·then: ldaps:// 호스트로 접속 정보를 만든다 → host 문구의 InvalidValueError다
    _bad("host", host="dc1.corp.test:636")


def test_connection_is_frozen() -> None:
    """접속 정보는 만든 뒤 바꿀 수 없다."""
    # when: 필드를 바꾸려 한다
    connection = make_directory_connection()

    # then: 오류가 난다
    with pytest.raises(dataclasses.FrozenInstanceError):
        connection.port = 389  # type: ignore[misc]


@pytest.mark.parametrize(
    ("port", "ok"), [(0, False), (1, True), (65535, True), (65536, False), (-1, False)]
)
def test_port_outside_range_is_rejected_with_field_name(port: int, ok: bool) -> None:
    """포트는 1~65535만 받고 벗어나면 port 필드 이름이 든 오류다.

    테스트 코드: IN-019
    """
    # when·then: 경계 값(0·1·65535·65536)으로 접속 정보를 만든다
    # → 1과 65535는 받고 0과 65536은 port 문구로 거절된다
    if ok:
        assert make_directory_connection(port=port).port == port
    else:
        _bad("port", port=port)


@pytest.mark.parametrize(
    ("value", "ok"), [(0, False), (1, True), (30, True), (31, False), (-1, False)]
)
def test_connect_timeout_outside_1_to_30_is_rejected(value: int, ok: bool) -> None:
    """연결 제한 시간은 1~30초만 받는다.

    테스트 코드: IN-019
    """
    # when·then: 경계 값(0·1·30·31)으로 접속 정보를 만든다
    # → 1과 30은 받고 0과 31은 connect_timeout_seconds 문구로 거절된다
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
    """바인드 계정은 DN·UPN·DOMAIN\name 형식과 256자를 받는다.

    테스트 코드: IN-019
    """
    # when: 여러 형식의 계정으로 접속 정보를 만든다
    bind_account = make_directory_connection(bind_account=account).bind_account
    # then: 그대로 받아진다
    assert bind_account == account


@pytest.mark.parametrize("account", ["", "x" * 257, "svc\x01", "svc\n", "svc\x00", "svc\x7f"])
def test_bind_account_empty_too_long_or_control_char_is_rejected(account: str) -> None:
    """바인드 계정이 비었거나 257자거나 제어문자가 있으면 bind_account 필드 이름이 든 오류다.

    테스트 코드: IN-019
    """
    # when·then: 빈 값·257자·제어문자 계정으로 접속 정보를 만든다
    # → bind_account 문구의 InvalidValueError다
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
    """사용자 필터는 {login_id} 한 번과 바깥 괄호 짝을 요구한다.

    테스트 코드: IN-018
    """
    # when·then: 괄호·{login_id} 규칙을 어긴 필터로 접속 정보를 만든다
    # → user_filter 문구의 InvalidValueError다
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
    """{login_id}가 한 번 있고 괄호가 맞는 필터는 받는다.

    테스트 코드: IN-018
    """
    # when: 올바른 필터로 접속 정보를 만든다
    actual = make_directory_connection(user_filter=user_filter).user_filter
    # then: 그대로 받아진다
    assert actual == user_filter


def test_user_filter_length_limit_is_512() -> None:
    """사용자 필터는 512자까지 받고 513자는 거절한다.

    테스트 코드: IN-018
    """

    # when: 512자와 513자 필터로 접속 정보를 만든다
    def filter_of_length(total: int) -> str:
        return "(cn={login_id}" + "x" * (total - len("(cn={login_id})")) + ")"

    # then: 512자는 받고 513자는 user_filter 문구로 거절된다
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
    """폐지된 입력(서버 URL·바인드 템플릿 등)은 접속 정보 필드가 아니다."""
    assert removed not in {f.name for f in dataclasses.fields(DirectoryConnection)}
    # when·then: 폐지된 필드로 접속 정보를 만든다 → TypeError다
    with pytest.raises(TypeError):
        make_directory_connection(**{removed: "x"})


def test_same_endpoint_and_account_compares_host_port_security_and_account_only() -> None:
    """엔드포인트·계정 비교는 호스트·포트·보안 연결·계정만 본다."""
    # when: 다른 필드만 다른 접속 정보를 비교한다
    base = make_directory_connection()

    # then: 같은 엔드포인트로 본다
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
    """빈 값·공백뿐·NUL·257자 바인드 비밀번호는 bind_password 필드 이름이 든 오류다.

    테스트 코드: IN-020
    """
    # when: 그런 값으로 바인드 비밀번호를 만든다
    with pytest.raises(InvalidValueError) as caught:
        bind_password_of(raw)

    # then: bind_password 문구의 InvalidValueError다
    assert "bind_password" in str(caught.value)


def test_bind_password_of_accepts_the_longest_value_and_keeps_spaces() -> None:
    """256자 바인드 비밀번호는 앞뒤 공백을 지우지 않고 그대로 받는다.

    테스트 코드: IN-020
    """
    # when: 공백이 앞뒤에 있는 256자 값으로 만든다
    actual = bind_password_of("a" * 256).reveal()
    # then: 공백이 그대로 남는다
    assert actual == "a" * 256
    assert bind_password_of(" pw with spaces ").reveal() == " pw with spaces "


def test_settings_carry_connection_and_password() -> None:
    """설정은 접속 정보와 비밀번호를 함께 가진다."""
    # when: 설정을 만든다
    settings = make_directory_settings()

    # then: 접속 정보와 비밀번호를 꺼낼 수 있다
    assert settings.connection == make_directory_connection()
    assert settings.bind_password.reveal() == BIND_PASSWORD
    assert isinstance(settings, DirectorySettings)


def test_settings_repr_hides_bind_password() -> None:
    """설정의 repr에는 바인드 비밀번호가 없다."""
    # when: repr을 만든다
    settings = DirectorySettings(
        connection=make_directory_connection(), bind_password=Password(BIND_PASSWORD)
    )

    # then: 비밀번호가 보이지 않는다
    assert BIND_PASSWORD not in repr(settings)
    assert BIND_PASSWORD not in str(settings)


def test_sealed_secret_repr_hides_the_token() -> None:
    """봉인된 비밀번호의 repr에는 토큰이 없다."""
    # when: repr을 만든다
    sealed = SealedSecret("gAAAAA-token-value")

    # then: 토큰이 보이지 않는다
    assert "gAAAAA-token-value" not in repr(sealed)
    assert "gAAAAA-token-value" not in str(sealed)
    assert sealed.token == "gAAAAA-token-value"  # noqa: S105 - 가짜 값
