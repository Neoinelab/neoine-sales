"""AD 설정 요청·응답 스키마(AC2·AC4·AC15): 입력 7개, 구 필드 거부, 비밀번호 유지 표시, 로그인 응답.

값의 범위 검증은 도메인이 하므로(422 invalid-value) 여기서는 모양(필수·타입·구 필드)과
도메인 변환을 본다.
"""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.application.auth.fallback_login import DirectoryWarning, DirectoryWarningStage
from app.application.auth.issue_session import IssuedSession
from app.application.auth.messages import FALLBACK_MESSAGES
from app.domain.auth.principal import Role
from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectorySettings, DirectorySettingsDraft, SecurityMode
from app.web.schemas.auth import (
    DirectoryWarningResponse,
    LoginResponse,
    PrincipalResponse,
)
from app.web.schemas.auth_directory import DirectorySettingsRequest, DirectorySettingsResponse
from app.web.schemas.settings_directory import (
    DirectorySettingsTestRequest,
    DirectorySettingsUpdateRequest,
    DirectoryTestResultResponse,
)
from tests.factories import NOW
from tests.factories_auth import BIND_ACCOUNT, BIND_PASSWORD, USER_FILTER, make_principal

OLD_FIELDS = [
    "server_urls",
    "use_starttls",
    "ca_cert_pem",
    "bind_template",
    "base_dn",
    "display_name_attribute",
    "email_attribute",
    "receive_timeout_seconds",
]
CONNECTION = {
    "host": "dc1.corp.test",
    "port": 636,
    "security": "ssl",
    "bind_account": BIND_ACCOUNT,
    "user_filter": USER_FILTER,
    "connect_timeout_seconds": 5,
}


def _body(**extra: Any) -> dict[str, Any]:  # noqa: ANN401
    return {**CONNECTION, **extra}


def test_setup_request_converts_to_domain_settings() -> None:
    request = DirectorySettingsRequest.model_validate(_body(bind_password=BIND_PASSWORD))

    settings = request.to_domain()

    assert isinstance(settings, DirectorySettings)
    assert (settings.connection.host, settings.connection.port) == ("dc1.corp.test", 636)
    assert settings.connection.security is SecurityMode.SSL
    assert settings.connection.bind_account == BIND_ACCOUNT
    assert settings.bind_password.reveal() == BIND_PASSWORD
    assert BIND_PASSWORD not in repr(request)  # SecretStr 마스킹


def test_setup_request_defaults_the_timeout_to_five_seconds() -> None:
    body = _body(bind_password=BIND_PASSWORD)
    del body["connect_timeout_seconds"]

    assert (
        DirectorySettingsRequest.model_validate(body).to_domain().connection.connect_timeout_seconds
        == 5
    )


@pytest.mark.parametrize("old_field", OLD_FIELDS)
@pytest.mark.parametrize("model", [DirectorySettingsRequest, DirectorySettingsTestRequest])
def test_old_fields_are_rejected_as_unknown(
    old_field: str, model: type[DirectorySettingsRequest | DirectorySettingsTestRequest]
) -> None:
    with pytest.raises(ValidationError) as caught:
        model.model_validate(_body(bind_password=BIND_PASSWORD, **{old_field: "x"}))

    assert old_field in str(caught.value)


@pytest.mark.parametrize("old_field", OLD_FIELDS)
def test_old_fields_are_rejected_by_the_update_request(old_field: str) -> None:
    with pytest.raises(ValidationError):
        DirectorySettingsUpdateRequest.model_validate(
            _body(expected_revision=1, **{old_field: "x"})
        )


def test_setup_request_requires_bind_password() -> None:
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body())

    assert "bind_password" in str(caught.value)


@pytest.mark.parametrize("security", ["tls", "SSL", "", "ldaps", 1])
def test_security_must_be_none_ssl_or_starttls(security: object) -> None:
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body(bind_password="x", security=security))  # noqa: S106 - 가짜 값

    assert "security" in str(caught.value)


@pytest.mark.parametrize("security", ["none", "ssl", "starttls"])
def test_every_security_mode_is_accepted(security: str) -> None:
    request = DirectorySettingsRequest.model_validate(
        _body(bind_password="x", security=security, port=389)  # noqa: S106 - 가짜 값
    )

    assert request.to_domain().connection.security is SecurityMode(security)


@pytest.mark.parametrize("field", ["port", "connect_timeout_seconds"])
@pytest.mark.parametrize("value", ["636", 636.5, None, True])
def test_numbers_must_be_strict_integers(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body(bind_password="x", **{field: value}))  # noqa: S106 - 가짜 값

    assert field in str(caught.value)


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"port": 0}, "port"),
        ({"port": 65536}, "port"),
        ({"connect_timeout_seconds": 31}, "connect_timeout_seconds"),
        ({"host": "ldaps://dc1"}, "host"),
        ({"bind_account": ""}, "bind_account"),
        ({"user_filter": "no-placeholder"}, "user_filter"),
        ({"bind_password": ""}, "bind_password"),
        ({"bind_password": "pw\x00"}, "bind_password"),
    ],
)
def test_value_violations_are_domain_errors_naming_the_field(
    override: dict[str, Any], field: str
) -> None:
    request = DirectorySettingsRequest.model_validate(_body(**{"bind_password": "x", **override}))

    with pytest.raises(InvalidValueError) as caught:
        request.to_domain()

    assert field in str(caught.value)


def test_test_request_without_bind_password_means_keep() -> None:
    request = DirectorySettingsTestRequest.model_validate(_body())

    draft = request.to_draft()

    assert isinstance(draft, DirectorySettingsDraft)
    assert draft.bind_password is None
    assert request.to_password() is None


def test_test_request_with_null_bind_password_also_means_keep() -> None:
    draft = DirectorySettingsTestRequest.model_validate(_body(bind_password=None)).to_draft()

    assert draft.bind_password is None


def test_test_request_with_a_bind_password_carries_it() -> None:
    request = DirectorySettingsTestRequest.model_validate(
        _body(bind_password=BIND_PASSWORD, password="pw-root")  # noqa: S106 - 가짜 값
    )

    assert request.to_draft().bind_password is not None
    assert request.to_draft().bind_password.reveal() == BIND_PASSWORD  # type: ignore[union-attr]
    assert request.to_password() is not None
    assert BIND_PASSWORD not in repr(request)


@pytest.mark.parametrize("empty", ["", "   ", "pw\x00x", "p" * 257])
def test_an_empty_bind_password_is_a_value_violation_not_keep(empty: str) -> None:
    request = DirectorySettingsTestRequest.model_validate(_body(bind_password=empty))

    with pytest.raises(InvalidValueError) as caught:
        request.to_draft()

    assert "bind_password" in str(caught.value)


def test_test_request_has_no_expected_revision() -> None:
    with pytest.raises(ValidationError):
        DirectorySettingsTestRequest.model_validate(_body(expected_revision=1))


def test_update_request_accepts_a_null_revision_for_creating() -> None:
    request = DirectorySettingsUpdateRequest.model_validate(
        _body(bind_password=BIND_PASSWORD, expected_revision=None)
    )

    assert request.expected_revision is None


def test_update_request_accepts_an_integer_revision() -> None:
    assert (
        DirectorySettingsUpdateRequest.model_validate(_body(expected_revision=3)).expected_revision
        == 3
    )


@pytest.mark.parametrize("revision", [0, -1, "1", 1.5, True])
def test_update_request_rejects_an_invalid_revision(revision: object) -> None:
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsUpdateRequest.model_validate(_body(expected_revision=revision))

    assert "expected_revision" in str(caught.value)


def test_update_request_requires_the_revision_key() -> None:
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsUpdateRequest.model_validate(_body())

    assert "expected_revision" in str(caught.value)


def test_settings_response_has_the_documented_fields_and_no_password() -> None:
    fields = set(DirectorySettingsResponse.model_fields)

    assert fields == {
        "host",
        "port",
        "security",
        "bind_account",
        "bind_credential_status",
        "user_filter",
        "connect_timeout_seconds",
        "base_dn",
        "revision",
        "updated_at",
        "updated_by",
    }
    assert not any("password" in name for name in fields)


def test_test_result_response_carries_the_discovered_base_dn() -> None:
    assert set(DirectoryTestResultResponse.model_fields) == {
        "success",
        "stage",
        "message",
        "base_dn",
    }


def test_login_response_adds_the_directory_warning_to_the_principal_fields() -> None:
    assert set(PrincipalResponse.model_fields) < set(LoginResponse.model_fields)
    assert set(LoginResponse.model_fields) - set(PrincipalResponse.model_fields) == {
        "directory_warning"
    }
    assert set(DirectoryWarningResponse.model_fields) == {"stage", "message"}


def _outcome(role: Role, warning: DirectoryWarning | None) -> SimpleNamespace:
    principal = make_principal("boss", role)
    session = IssuedSession(token="tok", expires_at=NOW + timedelta(hours=8), principal=principal)  # noqa: S106
    return SimpleNamespace(session=session, directory_warning=warning)


def test_login_response_without_a_warning_has_null() -> None:
    response = LoginResponse.from_outcome(_outcome(Role.SALES, None))  # type: ignore[arg-type]

    assert response.directory_warning is None
    assert response.subject == "boss"
    assert response.model_dump()["directory_warning"] is None


def test_login_response_carries_the_warning_stage_and_message() -> None:
    warning = DirectoryWarning(
        stage=DirectoryWarningStage.CONNECT,
        message=FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )

    response = LoginResponse.from_outcome(_outcome(Role.ADMIN, warning))  # type: ignore[arg-type]

    assert response.directory_warning is not None
    assert response.directory_warning.stage == "connect"
    assert response.directory_warning.message == FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT]
    assert "tok" not in response.model_dump_json()  # 세션 토큰은 본문에 없다
