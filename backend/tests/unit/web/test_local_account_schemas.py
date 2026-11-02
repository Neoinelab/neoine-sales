"""local 계정 요청 스키마 (AC-4·6·7·10·11·15): strict 키, PATCH 의미(UNSET/None), 비밀번호 마스킹.

스키마 위치·이름(구현자가 따른다):
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
    assert AuthModeRequest.model_validate({"mode": mode.value}).mode is mode


@pytest.mark.parametrize(
    "body", [{}, {"mode": "oidc"}, {"mode": "LOCAL"}, {"mode": 1}, {"mode": "ad", "x": 1}]
)
def test_auth_mode_request_rejects_everything_else(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        AuthModeRequest.model_validate(body)


# ---- 프로필 PATCH (UNSET / None) ----


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_without_keys_changes_nothing(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    changes = schema.model_validate({}).to_changes()

    assert changes == ProfileChanges()
    assert (changes.display_name, changes.email, changes.phone) == (UNSET, UNSET, UNSET)


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_null_means_clear_and_missing_means_keep(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    changes = schema.model_validate({"email": None, "phone": "010-1234-5678"}).to_changes()

    assert changes.email is None
    assert changes.phone == "010-1234-5678"
    assert changes.display_name is UNSET


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_carries_values_as_given(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    changes = schema.model_validate({"display_name": "  김영업 ", "email": " A@B.co "}).to_changes()

    assert (changes.display_name, changes.email) == ("  김영업 ", " A@B.co ")  # 정규화는 도메인


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
@pytest.mark.parametrize(
    "key", ["login_id", "role", "id", "password", "auth_mode", "editable", "unknown"]
)
def test_me_profile_request_rejects_login_id_and_role_keys(
    schema: type[MyProfileRequest | UserProfileRequest], key: str
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate({key: "x"})


@pytest.mark.parametrize("schema", [MyProfileRequest, UserProfileRequest])
def test_profile_request_rejects_non_string_values(
    schema: type[MyProfileRequest | UserProfileRequest],
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate({"phone": 1012345678})


# ---- 비밀번호 요청 ----


def test_password_requests_mask_secret_in_repr() -> None:
    requests = [
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "password": SECRET}),
        UserPasswordRequest.model_validate({"password": SECRET}),
        MyPasswordRequest.model_validate(
            {"current_password": SECRET, "new_password": SECRET + "2"}
        ),
        SetupAdminRequest.model_validate({"login_id": "kim", "password": SECRET}),
    ]

    for request in requests:
        assert SECRET not in repr(request)
        assert SECRET not in str(request)
        assert SECRET not in request.model_dump_json()


def test_user_request_password_is_optional_and_defaults_to_none() -> None:
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales"})

    assert (request.password, request.email, request.phone) == (None, None, None)


def test_user_request_carries_email_and_phone_as_given() -> None:
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "email": " A@B.co ", "phone": " 02-123-4567 "}
    )

    assert (request.email, request.phone) == (" A@B.co ", " 02-123-4567 ")


def test_setup_admin_request_profile_fields_are_optional() -> None:
    request = SetupAdminRequest.model_validate({"login_id": "kim", "password": SECRET})

    assert (request.display_name, request.email, request.phone) == (None, None, None)


def test_setup_admin_request_still_rejects_unknown_fields() -> None:
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
    schema, body = schema_body
    with pytest.raises(ValidationError):
        schema.model_validate(body)


def test_password_requests_accept_exactly_the_maximum_length() -> None:
    UserPasswordRequest.model_validate({"password": "x" * PASSWORD_MAX})


@pytest.mark.parametrize("body", [{}, {"current_password": "x"}, {"new_password": "x"}])
def test_my_password_request_needs_both_fields(body: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        MyPasswordRequest.model_validate(body)


def test_password_requests_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        UserPasswordRequest.model_validate({"password": SECRET, "login_id": "kim"})
    with pytest.raises(ValidationError):
        MyPasswordRequest.model_validate(
            {"current_password": SECRET, "new_password": SECRET, "extra": 1}
        )
