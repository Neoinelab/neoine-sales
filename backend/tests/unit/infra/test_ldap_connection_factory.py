"""T-A11: 기본 연결 팩토리가 설정으로 서버를 만든다(AC8). 접속하지 않는다.

SSL·StartTLS는 서버 인증서를 검증하지 않는다(ssl.CERT_NONE). 서버는 호스트 하나와 포트 하나뿐이다.
"""

import ssl

import pytest
from ldap3 import SIMPLE

from app.domain.directory.settings import SecurityMode
from app.infra.auth.ldap import default_connection_factory
from tests.factories_directory import make_directory_settings


def test_ssl_builds_an_ldaps_server_without_certificate_validation() -> None:
    settings = make_directory_settings(
        host="dc1.corp.test", port=3269, security=SecurityMode.SSL, connect_timeout_seconds=7
    )

    connection = default_connection_factory(settings, "cn=svc,dc=corp", "pw-dummy")

    server = connection.server
    assert (server.host, server.port, server.ssl) == ("dc1.corp.test", 3269, True)
    assert server.tls.validate == ssl.CERT_NONE
    assert server.tls.ca_certs_data is None  # CA 인증서 입력은 없다
    assert server.connect_timeout == 7
    assert connection.receive_timeout == 10  # 고정 10초
    assert connection.user == "cn=svc,dc=corp"
    assert connection.authentication == SIMPLE
    assert connection.read_only is True
    assert connection.raise_exceptions is False
    assert connection.server_pool is None


def test_starttls_connects_in_plain_text_first_and_keeps_validation_off() -> None:
    settings = make_directory_settings(port=389, security=SecurityMode.STARTTLS)

    connection = default_connection_factory(settings, "u", "p")

    assert (connection.server.port, connection.server.ssl) == (389, False)
    assert connection.server.tls.validate == ssl.CERT_NONE


def test_none_is_plain_ldap() -> None:
    settings = make_directory_settings(port=389, security=SecurityMode.NONE)

    connection = default_connection_factory(settings, "u", "p")

    assert (connection.server.port, connection.server.ssl) == (389, False)


@pytest.mark.parametrize("host", ["10.0.0.5", "::1", "2001:db8::1"])
def test_ip_literals_are_passed_through_unbracketed(host: str) -> None:
    connection = default_connection_factory(make_directory_settings(host=host), "u", "p")

    assert connection.server.host == host


def test_timeouts_use_connect_setting_and_fixed_receive_10s() -> None:
    connection = default_connection_factory(
        make_directory_settings(connect_timeout_seconds=3), "u", "p"
    )

    assert connection.server.connect_timeout == 3
    assert connection.receive_timeout == 10


def test_the_factory_takes_the_password_from_the_argument_not_the_service_settings() -> None:
    """사용자 바인드에도 같은 팩토리를 쓰므로 비밀번호는 인자로 받은 값이다."""
    connection = default_connection_factory(make_directory_settings(), "cn=kim,dc=corp", "user-pw")

    assert connection.user == "cn=kim,dc=corp"
    assert connection.password == "user-pw"  # noqa: S105 - 가짜 값
