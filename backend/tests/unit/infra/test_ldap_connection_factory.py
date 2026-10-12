"""T-A11: 기본 연결 팩토리가 설정으로 TLS 검증 서버를 만든다(DIR-3·4). 접속하지 않는다."""

import ssl

from ldap3 import SIMPLE

from app.domain.directory.settings import DirectoryUrl
from app.infra.auth.ldap import default_connection_factory
from tests.factories_auth import DUMMY_PEM, make_directory_settings


def test_default_factory_builds_verified_tls_servers_from_settings() -> None:
    settings = make_directory_settings(
        server_urls=(DirectoryUrl.parse("ldaps://dc1.corp.test:3269"),),
        ca_cert_pem=DUMMY_PEM,
        connect_timeout_seconds=7,
        receive_timeout_seconds=22,
    )

    connection = default_connection_factory(settings, "cn=kim,dc=corp", "pw-dummy")

    server = connection.server
    assert (server.host, server.port, server.ssl) == ("dc1.corp.test", 3269, True)
    assert server.tls.validate == ssl.CERT_REQUIRED
    assert server.tls.ca_certs_data == DUMMY_PEM
    assert server.connect_timeout == 7
    assert connection.receive_timeout == 22
    assert connection.user == "cn=kim,dc=corp"
    assert connection.authentication == SIMPLE
    assert connection.read_only is True
    assert connection.raise_exceptions is False
    assert connection.server_pool is None


def test_default_factory_uses_system_ca_when_no_pem_is_configured() -> None:
    connection = default_connection_factory(make_directory_settings(), "u", "p")

    assert connection.server.tls.validate == ssl.CERT_REQUIRED
    assert connection.server.tls.ca_certs_data is None


def test_default_factory_keeps_certificate_validation_for_starttls_servers() -> None:
    settings = make_directory_settings(
        server_urls=(DirectoryUrl.parse("ldap://dc1.corp.test"),), use_starttls=True
    )

    connection = default_connection_factory(settings, "u", "p")

    assert (connection.server.port, connection.server.ssl) == (389, False)
    assert connection.server.tls.validate == ssl.CERT_REQUIRED


def test_default_factory_keeps_tls_validation_and_timeouts_for_several_urls() -> None:
    """여러 URL이어도 서버마다 검증·타임아웃이 유지되고, 무한 대기를 만드는 소진형 풀을 쓰지 않는다.

    (ServerPool(active=True, exhaust=True)은 모든 서버가 실패하면 영원히 기다린다. 실제 도달 불가
    동작은 test_ldap_unreachable_servers.py가 검증한다. 풀 유무는 구현 선택이라 가정하지 않는다.)
    """
    settings = make_directory_settings(
        server_urls=(
            DirectoryUrl.parse("ldaps://dc1.corp.test"),
            DirectoryUrl.parse("ldaps://dc2.corp.test:3269"),
        ),
        ca_cert_pem=DUMMY_PEM,
        connect_timeout_seconds=3,
    )

    connection = default_connection_factory(settings, "u", "p")

    pool = connection.server_pool
    assert pool is None or not (pool.active is True and pool.exhaust is True)
    servers = list(pool.servers) if pool is not None else [connection.server]
    assert (servers[0].host, servers[0].port) == ("dc1.corp.test", 636)
    for server in servers:
        assert server.tls.validate == ssl.CERT_REQUIRED
        assert server.tls.ca_certs_data == DUMMY_PEM
        assert server.connect_timeout == 3


def test_default_factory_allows_anonymous_connection_objects_for_probe() -> None:
    connection = default_connection_factory(make_directory_settings(), None, None)

    assert connection.user is None
    assert connection.closed
