"""POST /users 요청 스키마의 선택 display_name. 길이·NUL 판단은 도메인이 한다."""

import pytest
from pydantic import ValidationError

from app.domain.auth.principal import NAME_MAX, Role
from app.web.schemas.user import UserRequest


def test_display_name_is_optional_and_defaults_to_none() -> None:
    """등록 본문의 이름은 선택이고 기본은 None이다

    테스트 코드: US-012
    """
    # when: 이름 없는 본문을 검증한다
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales"})

    # then: 이름이 None이다
    assert request.display_name is None
    assert request.role is Role.SALES


def test_display_name_accepts_null() -> None:
    """이름에 null을 줄 수 있다

    테스트 코드: US-012
    """
    # when: 이름이 null인 본문을 검증한다
    request = UserRequest.model_validate({"login_id": "kim", "role": "sales", "display_name": None})

    # then: 이름이 None이다
    assert request.display_name is None


def test_display_name_is_carried_as_given() -> None:
    """스키마는 이름을 가공하지 않고 그대로 전달한다"""
    # when: 공백이 있는 이름의 본문을 검증한다
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "display_name": "  김영업 "}
    )

    # then: 이름이 입력 그대로다
    assert request.display_name == "  김영업 "


def test_overlong_display_name_is_left_to_the_domain_not_the_schema() -> None:
    """이름 길이 판단은 스키마가 아니라 도메인이 한다"""
    # when: 201자 이름의 본문을 검증한다
    request = UserRequest.model_validate(
        {"login_id": "kim", "role": "sales", "display_name": "가" * (NAME_MAX + 1)}
    )

    # then: 스키마는 거절하지 않는다
    assert len(request.display_name or "") == NAME_MAX + 1


def test_display_name_rejects_a_non_string() -> None:
    """이름이 문자열이 아니면 거절된다

    테스트 코드: US-016
    """
    # when: 숫자 이름의 본문을 검증한다
    with pytest.raises(ValidationError):
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "display_name": 7})
    # then: 검증 오류다


def test_unknown_fields_are_still_rejected() -> None:
    """모르는 필드가 있는 본문은 거절된다

    테스트 코드: US-016
    """
    # when: 모르는 필드가 있는 본문을 검증한다
    with pytest.raises(ValidationError):
        UserRequest.model_validate({"login_id": "kim", "role": "sales", "nickname": "k"})
    # then: 검증 오류다
