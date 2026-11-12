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
    """최초 설정 요청은 도메인 설정으로 바뀌고 비밀번호는 마스킹된다."""
    # given: 바인드 비밀번호가 든 요청
    request = DirectorySettingsRequest.model_validate(_body(bind_password=BIND_PASSWORD))

    # when: 도메인 설정으로 바꾼다
    settings = request.to_domain()

    # then: 접속 값이 옮겨지고 repr에 비밀번호가 없다
    assert isinstance(settings, DirectorySettings)
    assert (settings.connection.host, settings.connection.port) == ("dc1.corp.test", 636)
    assert settings.connection.security is SecurityMode.SSL
    assert settings.connection.bind_account == BIND_ACCOUNT
    assert settings.bind_password.reveal() == BIND_PASSWORD
    assert BIND_PASSWORD not in repr(request)  # SecretStr 마스킹


def test_setup_request_defaults_the_timeout_to_five_seconds() -> None:
    """연결 제한 시간을 빼면 5초가 기본이다."""
    # given: 연결 제한 시간이 없는 요청 본문
    body = _body(bind_password=BIND_PASSWORD)
    del body["connect_timeout_seconds"]

    # when: 연결 제한 시간 없이 도메인 설정으로 바꾼다
    connect_timeout_seconds = (
        DirectorySettingsRequest.model_validate(body).to_domain().connection.connect_timeout_seconds
    )
    # then: 제한 시간이 5초다
    assert connect_timeout_seconds == 5


@pytest.mark.parametrize("old_field", OLD_FIELDS)
@pytest.mark.parametrize("model", [DirectorySettingsRequest, DirectorySettingsTestRequest])
def test_old_fields_are_rejected_as_unknown(
    old_field: str, model: type[DirectorySettingsRequest | DirectorySettingsTestRequest]
) -> None:
    """폐지된 필드(서버 URL·CA 인증서 등)는 모르는 필드로 거절된다.

    테스트 코드: IN-021
    """
    # when: 폐지된 필드가 든 본문을 검증한다
    with pytest.raises(ValidationError) as caught:
        model.model_validate(_body(bind_password=BIND_PASSWORD, **{old_field: "x"}))

    # then: ValidationError다
    assert old_field in str(caught.value)


@pytest.mark.parametrize("old_field", OLD_FIELDS)
def test_old_fields_are_rejected_by_the_update_request(old_field: str) -> None:
    """저장 요청도 폐지된 필드를 거절한다.

    테스트 코드: IN-021
    """
    # when·then: 폐지된 필드가 든 저장 본문을 검증한다 → ValidationError다
    with pytest.raises(ValidationError):
        DirectorySettingsUpdateRequest.model_validate(
            _body(expected_revision=1, **{old_field: "x"})
        )


def test_setup_request_requires_bind_password() -> None:
    """최초 설정 요청에는 바인드 비밀번호가 필수다."""
    # when: 바인드 비밀번호 없이 검증한다
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body())

    # then: bind_password 검증 오류다
    assert "bind_password" in str(caught.value)


@pytest.mark.parametrize("security", ["tls", "SSL", "", "ldaps", 1])
def test_security_must_be_none_ssl_or_starttls(security: object) -> None:
    """보안 연결은 none·ssl·starttls만 받는다.

    테스트 코드: IN-021
    """
    # when: 그 밖의 값으로 검증한다
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body(bind_password="x", security=security))  # noqa: S106 - 가짜 값

    # then: security 필드의 ValidationError다
    assert "security" in str(caught.value)


@pytest.mark.parametrize("security", ["none", "ssl", "starttls"])
def test_every_security_mode_is_accepted(security: str) -> None:
    """보안 연결 방식 세 가지를 모두 받는다."""
    # when: 방식을 지정해 요청을 만든다
    request = DirectorySettingsRequest.model_validate(
        _body(bind_password="x", security=security, port=389)  # noqa: S106 - 가짜 값
    )

    # then: 도메인 설정의 보안 방식이 지정한 값이다
    assert request.to_domain().connection.security is SecurityMode(security)


@pytest.mark.parametrize("field", ["port", "connect_timeout_seconds"])
@pytest.mark.parametrize("value", ["636", 636.5, None, True])
def test_numbers_must_be_strict_integers(field: str, value: object) -> None:
    """port·connect_timeout_seconds는 JSON 정수만 받는다(문자열·실수·불리언 거절).

    테스트 코드: IN-021
    """
    # when: 문자열·실수·null·불리언으로 검증한다
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsRequest.model_validate(_body(bind_password="x", **{field: value}))  # noqa: S106 - 가짜 값

    # then: 해당 필드의 ValidationError다
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
    """값 규칙 위반은 필드 이름이 든 도메인 오류로 바뀐다.

    테스트 코드: IN-016
    """
    # when: 범위·형식이 틀린 값을 도메인으로 바꾼다
    request = DirectorySettingsRequest.model_validate(_body(**{"bind_password": "x", **override}))

    with pytest.raises(InvalidValueError) as caught:
        request.to_domain()

    # then: 필드 이름이 든 InvalidValueError다
    assert field in str(caught.value)


def test_test_request_without_bind_password_means_keep() -> None:
    """연결 테스트 요청에 바인드 비밀번호가 없으면 저장된 값을 유지한다는 뜻이다."""
    # given: 바인드 비밀번호 없는 테스트 요청
    request = DirectorySettingsTestRequest.model_validate(_body())

    # when: 초안으로 바꾼다
    draft = request.to_draft()

    # then: 초안의 비밀번호와 별도 비밀번호가 None이다
    assert isinstance(draft, DirectorySettingsDraft)
    assert draft.bind_password is None
    assert request.to_password() is None


def test_test_request_with_null_bind_password_also_means_keep() -> None:
    """바인드 비밀번호가 null이어도 저장된 값을 유지한다는 뜻이다."""
    # when: 초안으로 바꾼다
    draft = DirectorySettingsTestRequest.model_validate(_body(bind_password=None)).to_draft()

    # then: 초안의 비밀번호가 None이다
    assert draft.bind_password is None


def test_test_request_with_a_bind_password_carries_it() -> None:
    """바인드 비밀번호를 주면 초안이 그 값을 가지고 repr에는 드러나지 않는다."""
    # when: 초안과 비밀번호를 꺼낸다
    request = DirectorySettingsTestRequest.model_validate(
        _body(bind_password=BIND_PASSWORD, password="pw-root")  # noqa: S106 - 가짜 값
    )

    # then: 값이 전달되고 repr에는 없다
    assert request.to_draft().bind_password is not None
    assert request.to_draft().bind_password.reveal() == BIND_PASSWORD  # type: ignore[union-attr]
    assert request.to_password() is not None
    assert BIND_PASSWORD not in repr(request)


@pytest.mark.parametrize("empty", ["", "   ", "pw\x00x", "p" * 257])
def test_an_empty_bind_password_is_a_value_violation_not_keep(empty: str) -> None:
    """빈 문자열·공백만·NUL·257자 바인드 비밀번호는 '유지'가 아니라 값 위반이다.

    테스트 코드: IN-020
    """
    # when: 그 값으로 초안을 만든다
    request = DirectorySettingsTestRequest.model_validate(_body(bind_password=empty))

    with pytest.raises(InvalidValueError) as caught:
        request.to_draft()

    # then: bind_password 문구의 InvalidValueError다
    assert "bind_password" in str(caught.value)


def test_test_request_has_no_expected_revision() -> None:
    """연결 테스트 요청에 expected_revision을 넣으면 거절된다.

    테스트 코드: IN-021
    """
    # when·then: expected_revision이 든 테스트 본문을 검증한다 → ValidationError다
    with pytest.raises(ValidationError):
        DirectorySettingsTestRequest.model_validate(_body(expected_revision=1))


def test_update_request_accepts_a_null_revision_for_creating() -> None:
    """신규 등록 수정 요청은 revision null을 받는다."""
    # when: revision을 null로 검증한다
    request = DirectorySettingsUpdateRequest.model_validate(
        _body(bind_password=BIND_PASSWORD, expected_revision=None)
    )

    # then: expected_revision이 None이다
    assert request.expected_revision is None


def test_update_request_accepts_an_integer_revision() -> None:
    """수정 요청은 정수 revision을 받는다."""
    # when: revision 3으로 검증한다
    expected_revision = DirectorySettingsUpdateRequest.model_validate(
        _body(expected_revision=3)
    ).expected_revision
    # then: expected_revision이 3이다
    assert expected_revision == 3


@pytest.mark.parametrize("revision", [0, -1, "1", 1.5, True])
def test_update_request_rejects_an_invalid_revision(revision: object) -> None:
    """expected_revision은 1 이상의 정수만 받는다.

    테스트 코드: IN-021
    """
    # when: 0·음수·문자열·실수·불리언으로 검증한다
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsUpdateRequest.model_validate(_body(expected_revision=revision))

    # then: expected_revision 필드의 ValidationError다
    assert "expected_revision" in str(caught.value)


def test_update_request_requires_the_revision_key() -> None:
    """저장 요청은 expected_revision 키가 필수다.

    테스트 코드: IN-021
    """
    # when: 키 없이 검증한다
    with pytest.raises(ValidationError) as caught:
        DirectorySettingsUpdateRequest.model_validate(_body())

    # then: expected_revision 필드의 ValidationError다
    assert "expected_revision" in str(caught.value)


def test_settings_response_has_the_documented_fields_and_no_password() -> None:
    """AD 설정 응답은 문서화된 11개 필드뿐이고 비밀번호 필드가 없다.

    테스트 코드: IN-001
    """
    # when: 응답 모델의 필드를 읽는다
    fields = set(DirectorySettingsResponse.model_fields)

    # then: 11개 필드이고 password가 든 이름이 없다
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
    """연결 테스트 결과는 success·stage·message·base_dn 네 필드다.

    테스트 코드: IN-042
    """
    # when: 결과 모델의 필드를 읽는다
    actual = set(DirectoryTestResultResponse.model_fields)
    # then: 네 필드다
    assert actual == {
        "success",
        "stage",
        "message",
        "base_dn",
    }


def test_login_response_adds_the_directory_warning_to_the_principal_fields() -> None:
    """로그인 응답은 Principal 필드에 directory_warning만 더한다."""
    # when: 두 응답 스키마의 필드를 비교한다
    actual = set(PrincipalResponse.model_fields)
    # then: 차이는 directory_warning 하나이고 경고는 stage·message뿐이다
    assert actual < set(LoginResponse.model_fields)
    assert set(LoginResponse.model_fields) - set(PrincipalResponse.model_fields) == {
        "directory_warning"
    }
    assert set(DirectoryWarningResponse.model_fields) == {"stage", "message"}


def _outcome(role: Role, warning: DirectoryWarning | None) -> SimpleNamespace:
    principal = make_principal("boss", role)
    session = IssuedSession(token="tok", expires_at=NOW + timedelta(hours=8), principal=principal)  # noqa: S106
    return SimpleNamespace(session=session, directory_warning=warning)


def test_login_response_without_a_warning_has_null() -> None:
    """경고가 없으면 로그인 응답의 directory_warning은 null이다."""
    # when: 경고 없는 결과로 응답을 만든다
    response = LoginResponse.from_outcome(_outcome(Role.SALES, None))  # type: ignore[arg-type]

    # then: directory_warning이 null이다
    assert response.directory_warning is None
    assert response.subject == "boss"
    assert response.model_dump()["directory_warning"] is None


def test_login_response_carries_the_warning_stage_and_message() -> None:
    """경고가 있으면 로그인 응답에 단계와 문구가 담기고 세션 토큰은 본문에 없다."""
    # given: 연결 단계 경고
    warning = DirectoryWarning(
        stage=DirectoryWarningStage.CONNECT,
        message=FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT],
    )

    # when: 경고가 있는 결과로 응답을 만든다
    response = LoginResponse.from_outcome(_outcome(Role.ADMIN, warning))  # type: ignore[arg-type]

    # then: stage·message가 담기고 토큰은 없다
    assert response.directory_warning is not None
    assert response.directory_warning.stage == "connect"
    assert response.directory_warning.message == FALLBACK_MESSAGES[DirectoryWarningStage.CONNECT]
    assert "tok" not in response.model_dump_json()  # 세션 토큰은 본문에 없다
