"""AC-25: POST /users 요청 스키마의 선택 display_name. 길이·NUL 판단은 도메인이 한다."""

import pytest
from pydantic import ValidationError

from app.domain.auth.principal import NAME_MAX, Role
from app.web.schemas.user import UserRequest


def test_display_name_is_optional_and_defaults_to_none() -> None:
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales"})

    assert request.display_name is None
    assert request.role is Role.SALES


def test_display_name_accepts_null() -> None:
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales", "display_name": None})

    assert request.display_name is None


def test_display_name_is_carried_as_given() -> None:
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "display_name": "  김영업 "}
    )

    assert request.display_name == "  김영업 "


def test_overlong_display_name_is_left_to_the_domain_not_the_schema() -> None:
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "display_name": "가" * (NAME_MAX + 1)}
    )

    assert len(request.display_name or "") == NAME_MAX + 1


def test_display_name_rejects_a_non_string() -> None:
    with pytest.raises(ValidationError):
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "display_name": 7})


def test_unknown_fields_are_still_rejected() -> None:
    with pytest.raises(ValidationError):
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "nickname": "k"})
