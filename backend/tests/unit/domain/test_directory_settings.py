"""T-D14~D21: DirectorySettings 검증(DS-1~5, DIR-3). 위반 메시지에는 영문 필드 이름이 들어간다."""

import dataclasses

import pytest

from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectorySettings, DirectoryUrl
from tests.factories_auth import DUMMY_PEM, make_directory_settings


def _bad(field: str, **overrides: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        make_directory_settings(**overrides)
    assert field in str(caught.value)


def test_valid_settings_have_documented_defaults() -> None:
    settings = make_directory_settings()

    assert settings.display_name_attribute == "displayName"
    assert settings.email_attribute == "mail"
    assert settings.connect_timeout_seconds == 5
    assert settings.receive_timeout_seconds == 10


def test_settings_are_frozen() -> None:
    settings = make_directory_settings()

    with pytest.raises(dataclasses.FrozenInstanceError):
        settings.base_dn = "dc=other"  # type: ignore[misc]


def test_plain_ldap_requires_starttls() -> None:
    urls = (DirectoryUrl.parse("ldap://dc1.corp.test"),)

    _bad("use_starttls", server_urls=urls, use_starttls=False)
    assert make_directory_settings(server_urls=urls, use_starttls=True).use_starttls


def test_mixed_ldaps_and_ldap_requires_starttls() -> None:
    urls = (DirectoryUrl.parse("ldaps://dc1.corp.test"), DirectoryUrl.parse("ldap://dc2.corp.test"))

    _bad("use_starttls", server_urls=urls, use_starttls=False)


def test_ldaps_only_does_not_need_starttls() -> None:
    assert not make_directory_settings(use_starttls=False).use_starttls


def test_server_url_list_size_and_duplicates() -> None:
    def urls(count: int) -> tuple[DirectoryUrl, ...]:
        return tuple(DirectoryUrl.parse(f"ldaps://dc{n}.corp.test") for n in range(count))

    _bad("server_urls", server_urls=())
    _bad("server_urls", server_urls=urls(6))
    assert len(make_directory_settings(server_urls=urls(1)).server_urls) == 1
    assert len(make_directory_settings(server_urls=urls(5)).server_urls) == 5
    same = DirectoryUrl.parse("ldaps://dc1.corp.test")
    _bad("server_urls", server_urls=(same, DirectoryUrl.parse("ldaps://DC1.corp.test:636")))


@pytest.mark.parametrize("field", ["bind_template", "user_filter"])
@pytest.mark.parametrize(
    "value",
    [
        "cn=nobody,dc=corp",
        "{login_id}{login_id}",
        "cn={login_id},ou={login_id}",
        "cn={}",
        "cn={other}",
    ],
)
def test_templates_need_exactly_one_placeholder(field: str, value: str) -> None:
    if field == "user_filter":
        value = f"({value})"
    _bad(field, **{field: value})


@pytest.mark.parametrize("field", ["bind_template", "user_filter"])
@pytest.mark.parametrize("extra", ["{", "}", "{0}", "{login_id!r}", "{login_id:>5}"])
def test_templates_reject_other_braces_and_format_specs(field: str, extra: str) -> None:
    value = f"(cn={{login_id}}{extra})" if field == "user_filter" else f"cn={{login_id}},{extra}"
    _bad(field, **{field: value})


@pytest.mark.parametrize(
    "template",
    ["cn={login_id},ou=users,dc=corp", "{login_id}@corp.test", "CORP\\{login_id}"],
)
def test_bind_template_forms_are_accepted(template: str) -> None:
    assert make_directory_settings(bind_template=template).bind_template == template


@pytest.mark.parametrize(
    ("template", "is_dn"),
    [
        ("cn={login_id},ou=users,dc=corp,dc=test", True),
        ("uid={login_id},dc=corp", True),
        ("{login_id}@corp.test", False),
        ("CORP\\{login_id}", False),
    ],
)
def test_bind_template_is_dn_distinguishes_dn_from_upn_and_domain_forms(
    template: str, is_dn: bool
) -> None:
    assert make_directory_settings(bind_template=template).bind_template_is_dn is is_dn


@pytest.mark.parametrize(
    "user_filter",
    [
        "uid={login_id}",
        "(uid={login_id}",
        "uid={login_id})",
        "(uid={login_id}))",
        "((uid={login_id})",
        ")uid={login_id}(",
        "(&(objectClass=user)(sAMAccountName={login_id})",
        "",
    ],
)
def test_filter_must_be_parenthesized_and_balanced(user_filter: str) -> None:
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
    assert make_directory_settings(user_filter=user_filter).user_filter == user_filter


@pytest.mark.parametrize("field", ["display_name_attribute", "email_attribute"])
@pytest.mark.parametrize(
    "value", ["", "1abc", "dis play", "a" * 65, "name;x", "na(me)", "한글", "-x"]
)
def test_attribute_names_are_validated(field: str, value: str) -> None:
    _bad(field, **{field: value})


@pytest.mark.parametrize(
    "value", ["displayName", "mail", "msDS-PrincipalName", "a", "A" + "b" * 63]
)
def test_valid_attribute_names_are_accepted(value: str) -> None:
    assert make_directory_settings(display_name_attribute=value).display_name_attribute == value


@pytest.mark.parametrize("char", ["\x00", "\x01", "\n", "\r", "\t", "\x7f"])
@pytest.mark.parametrize("field", ["bind_template", "base_dn", "user_filter"])
def test_settings_reject_control_characters(field: str, char: str) -> None:
    good = {
        "bind_template": "cn={login_id},dc=corp",
        "base_dn": "dc=corp",
        "user_filter": "(uid={login_id})",
    }[field]
    _bad(field, **{field: good.replace("dc=corp", f"dc={char}corp").replace("uid=", f"uid={char}")})


def _template_of_length(total: int) -> str:
    prefix = "cn={login_id},ou="
    return prefix + "x" * (total - len(prefix))


def test_bind_template_length_limit_is_256() -> None:
    assert len(make_directory_settings(bind_template=_template_of_length(256)).bind_template) == 256
    _bad("bind_template", bind_template=_template_of_length(257))


def test_base_dn_length_limit_is_512() -> None:
    assert make_directory_settings(base_dn="dc=" + "x" * 509).base_dn.endswith("x")
    _bad("base_dn", base_dn="dc=" + "x" * 510)


def test_user_filter_length_limit_is_512() -> None:
    def filter_of_length(total: int) -> str:
        return "(cn={login_id}" + "x" * (total - len("(cn={login_id})")) + ")"

    assert len(make_directory_settings(user_filter=filter_of_length(512)).user_filter) == 512
    _bad("user_filter", user_filter=filter_of_length(513))


def test_empty_base_dn_is_rejected() -> None:
    _bad("base_dn", base_dn="")


def test_ca_pem_accepts_certificate_block_with_newlines_and_chains() -> None:
    chain = DUMMY_PEM + DUMMY_PEM

    assert make_directory_settings(ca_cert_pem=DUMMY_PEM).ca_cert_pem == DUMMY_PEM
    assert make_directory_settings(ca_cert_pem=chain).ca_cert_pem == chain
    assert make_directory_settings(ca_cert_pem=None).ca_cert_pem is None


@pytest.mark.parametrize(
    "pem",
    [
        "not a certificate",
        "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n",
        "-----BEGIN CERTIFICATE-----\nAAAA\n",
        "AAAA\n-----END CERTIFICATE-----\n",
        "-----BEGIN CERTIFICATE-----\nAA\x00AA\n-----END CERTIFICATE-----\n",
        "-----BEGIN CERTIFICATE-----\nAA\x01AA\n-----END CERTIFICATE-----\n",
    ],
)
def test_ca_pem_must_be_certificate_block(pem: str) -> None:
    _bad("ca_cert_pem", ca_cert_pem=pem)


def _pem_of_length(total: int) -> str:
    head, tail = "-----BEGIN CERTIFICATE-----\n", "\n-----END CERTIFICATE-----\n"
    return head + "A" * (total - len(head) - len(tail)) + tail


def test_ca_pem_size_limit_is_64kb() -> None:
    assert (
        len(make_directory_settings(ca_cert_pem=_pem_of_length(65536)).ca_cert_pem or "") == 65536
    )
    _bad("ca_cert_pem", ca_cert_pem=_pem_of_length(65537))


@pytest.mark.parametrize(
    ("value", "ok"), [(0, False), (1, True), (30, True), (31, False), (-1, False)]
)
def test_connect_timeout_must_be_within_range(value: int, ok: bool) -> None:
    if ok:
        assert (
            make_directory_settings(connect_timeout_seconds=value).connect_timeout_seconds == value
        )
    else:
        _bad("connect_timeout_seconds", connect_timeout_seconds=value)


@pytest.mark.parametrize(
    ("value", "ok"), [(0, False), (1, True), (60, True), (61, False), (-1, False)]
)
def test_receive_timeout_must_be_within_range(value: int, ok: bool) -> None:
    if ok:
        assert (
            make_directory_settings(receive_timeout_seconds=value).receive_timeout_seconds == value
        )
    else:
        _bad("receive_timeout_seconds", receive_timeout_seconds=value)


def test_directory_settings_type_is_exported() -> None:
    assert isinstance(make_directory_settings(), DirectorySettings)
