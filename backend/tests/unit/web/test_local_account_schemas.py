"""local 계정 요청 스키마: strict 키, PATCH 의미(UNSET/None), 비밀번호 마스킹.

대상 스키마:
- app.web.schemas.auth: AuthModeRequest(mode: AuthMode),
  SetupAdminRequest(+display_name/email/phone)
- app.web.schemas.user: UserRequest(+email/phone/password), UserProfileRequest, UserPasswordRequest
- app.web.schemas.me: MyProfileRequest, MyPasswordRequest, MyProfileResponse
`to_changes()`는 보낸 키만 ProfileChanges에 싣는다(보내지 않음 = UNSET, null = 비움).
"""

import pytest
from pydantic import BaseModel, ValidationError

from app.domain.auth.credentials import PASSWORD_MAX
from app.domain.auth.mode import AuthMode
from app.domain.user.profile import UNSET, ProfileChanges
from app.web.schemas.auth import AuthModeRequest, SetupAdminRequest
from app.web.schemas.me import MyPasswordRequest, MyProfileRequest
from app.web.schemas.user import UserPasswordRequest, UserProfileRequest, UserRequest

SECRET = "Sup3r-Secret-Value"  # noqa: S105 - 가짜 값


# ---- AuthModeRequest ----


@pytest.mark.parametrize("mode", list(AuthMode))
def test_auth_mode_request_accepts_the_two_modes(mode: AuthMode) -> None:
    """인증 방식 요청은 ad와 local 두 값을 받는다."""
    # when: 방식 값 하나를 담아 요청을 검증한다
    request = AuthModeRequest.model_validate({"mode": mode.value})

    # then: 같은 방식으로 해석된다
    assert request.mode is mode


# ---- 프로필 PATCH (UNSET / None) ----


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_without_keys_changes_nothing(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    """키가 없는 내 정보 수정 요청은 아무것도 바꾸지 않는 변경(UNSET)이 된다(ME-R4, BDD 밖)."""
    # when: 키가 없는 요청을 변경 값으로 바꾼다
    changes = schema.model_validate({}).to_changes()

    # then: 모든 필드가 UNSET인 빈 변경이다
    assert changes == ProfileChanges()
    assert (changes.display_name, changes.email, changes.phone) == (UNSET, UNSET, UNSET)


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_null_means_clear_and_missing_means_keep(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    """null은 값을 비우고 빠진 키는 그대로 둔다(ME-R4, BDD 밖)."""
    # when: email은 null, phone은 값만 준 요청을 변경 값으로 바꾼다
    changes = schema.model_validate({"email": None, "phone": "010-1234-5678"}).to_changes()

    # then: email은 비움(None), phone은 값, 빠진 이름은 UNSET이다
    assert changes.email is None
    assert changes.phone == "010-1234-5678"
    assert changes.display_name is UNSET


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_carries_values_as_given(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    """요청 값은 가공 없이 그대로 변경 값으로 옮겨진다(정규화는 도메인, ME-R6, BDD 밖)."""
    # when: 앞뒤 공백이 있는 값을 준 요청을 변경 값으로 바꾼다
    changes = schema.model_validate({"display_name": "  김영업 ", "email": " A@B.co "}).to_changes()

    # then: 값이 가공 없이 그대로 옮겨진다
    assert (changes.display_name, changes.email) == ("  김영업 ", " A@B.co ")  # 정규화는 도메인


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
@pytest.mark.parametrize(
    "key", ["login_id", "role", "id", "password", "auth_mode", "editable", "unknown"]
)
def test_me_profile_request_rejects_login_id_and_role_keys(
    schema: type[MyProfileRequest | UserProfileRequest], key: str
) -> None:
    """내 정보 수정 요청은 login_id·role 키를 거절한다(ME-R5, BDD 밖)."""
    # when·then: 허용되지 않은 키를 넣어 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        schema.model_validate({key: "x"})


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_rejects_non_string_values(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    """문자열도 null도 아닌 값은 요청 형식 오류다(ME-R5, BDD 밖)."""
    # when·then: 숫자 phone으로 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        schema.model_validate({"phone": 1012345678})


# ---- 비밀번호 요청 ----


def test_password_requests_mask_secret_in_repr() -> None:
    """비밀번호 요청은 repr·str·JSON에 원문을 싣지 않는다(ME-R14, BDD 밖)."""
    # given: 비밀번호가 든 요청 모델 넷이 있다
    requests = [
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "password": SECRET}),
        UserPasswordRequest.model_validate({"password": SECRET}),
        MyPasswordRequest.model_validate(
            {"current_password": SECRET, "new_password": SECRET + "2"}
        ),
        SetupAdminRequest.model_validate({"login_id": "kim", "password": SECRET}),
    ]

    # when·then: repr·str·JSON 어디에도 비밀번호 원문이 없다
    for request in requests:
        assert SECRET not in repr(request)
        assert SECRET not in str(request)
        assert SECRET not in request.model_dump_json()


def test_user_request_password_is_optional_and_defaults_to_none() -> None:
    """사용자 요청의 비밀번호·이메일·전화가 선택이며 기본 None인지 확인한다."""
    # when: 아이디와 역할만 준 사용자 요청을 검증한다
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales"})

    # then: 비밀번호·이메일·전화가 모두 None이다
    assert (request.password, request.email, request.phone) == (None, None, None)


def test_user_request_carries_email_and_phone_as_given() -> None:
    """사용자 요청이 이메일·전화를 가공 없이 싣는지 확인한다."""
    # when: 공백이 붙은 이메일·전화를 준 사용자 요청을 검증한다
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "email": " A@B.co ", "phone": " 02-123-4567 "}
    )

    # then: 값이 그대로다
    assert (request.email, request.phone) == (" A@B.co ", " 02-123-4567 ")


def test_setup_admin_request_profile_fields_are_optional() -> None:
    """최초 admin 등록 요청의 이름·이메일·전화는 선택이며 기본 None이다."""
    # when: 아이디와 비밀번호만 담아 요청을 검증한다
    request = SetupAdminRequest.model_validate({"login_id": "kim", "password": SECRET})

    # then: 이름·이메일·전화가 모두 None이다
    assert (request.display_name, request.email, request.phone) == (None, None, None)


def test_setup_admin_request_still_rejects_unknown_fields() -> None:
    """최초 admin 등록 요청은 모르는 키를 거절한다."""
    # when·then: role 키를 더해 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        SetupAdminRequest.model_validate({"login_id": "kim", "password": SECRET, "role": "admin"})


@pytest.mark.parametrize(
    "schema_body",
    [
        (UserPasswordRequest, {"password": "x" * (PASSWORD_MAX + 1)}),
        (MyPasswordRequest, {"current_password": "x", "new_password": "x" * (PASSWORD_MAX + 1)}),
        (MyPasswordRequest, {"current_password": "x" * (PASSWORD_MAX + 1), "new_password": "x"}),
    ],
)
def test_password_requests_cap_the_length_at_the_domain_maximum(
    schema_body: tuple[type[BaseModel], dict[str, str]],
) -> None:
    """비밀번호 요청은 257자 이상을 요청 형식 오류로 거절한다(ME-R10, BDD 밖)."""
    # given: 최대 길이를 넘는 비밀번호 본문이 있다
    schema, body = schema_body
    # when·then: 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        schema.model_validate(body)


def test_password_requests_accept_exactly_the_maximum_length() -> None:
    """비밀번호 요청은 정확히 256자를 받아들인다(ME-R10, BDD 밖)."""
    # when·then: 정확히 최대 길이 비밀번호로 검증해도 오류가 나지 않는다
    UserPasswordRequest.model_validate({"password": "x" * PASSWORD_MAX})


@pytest.mark.parametrize("body", [{}, {"current_password": "x"}, {"new_password": "x"}])
def test_my_password_request_needs_both_fields(body: dict[str, str]) -> None:
    """비밀번호 변경 요청은 현재·새 비밀번호가 모두 있어야 한다(ME-R10, BDD 밖)."""
    # when·then: 필드가 빠진 본문으로 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        MyPasswordRequest.model_validate(body)


def test_password_requests_reject_unknown_fields() -> None:
    """비밀번호 요청은 알 수 없는 키를 거절한다(ME-R10, BDD 밖)."""
    # when·then: 알 수 없는 키가 든 사용자 비밀번호 요청을 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        UserPasswordRequest.model_validate({"password": SECRET, "login_id": "kim"})
    # when·then: 알 수 없는 키가 든 내 비밀번호 요청을 검증하면 ValidationError가 난다
    with pytest.raises(ValidationError):
        MyPasswordRequest.model_validate(
            {"current_password": SECRET, "new_password": SECRET, "extra": 1}
        )
