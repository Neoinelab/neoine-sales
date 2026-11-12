"""저장 위치 요청 스키마(P2b): 경로 형식·길이 판단은 도메인이 하고 스키마는 모양만 본다."""

import pytest
from pydantic import ValidationError

from app.web.schemas.storage import StorageSettingsRequest


def test_path_is_carried_as_given() -> None:
    """요청 스키마는 경로를 가공하지 않고 그대로 싣는다."""
    # when: 공백·중복 슬래시가 든 경로를 검증한다
    request = StorageSettingsRequest.model_validate({"path": "  /data//files/ "})

    # then: 입력 그대로다
    assert request.path == "  /data//files/ "


def test_an_overlong_path_is_left_to_the_domain_not_the_schema() -> None:
    """너무 긴 경로의 판단은 스키마가 아니라 도메인이 한다.

    테스트 코드: IN-056
    """
    # when: 5001자 경로를 검증한다
    request = StorageSettingsRequest.model_validate({"path": "/" + "a" * 5000})

    # then: 스키마는 통과시킨다
    assert len(request.path) == 5001


def test_an_empty_path_is_left_to_the_domain_not_the_schema() -> None:
    """빈 경로의 판단도 도메인이 한다.

    테스트 코드: IN-056
    """
    # when: 빈 문자열을 검증한다
    path = StorageSettingsRequest.model_validate({"path": ""}).path
    # then: 스키마는 통과시킨다
    assert path == ""


def test_the_json_schema_has_no_length_constraint_so_the_domain_message_is_returned() -> None:
    """JSON 스키마에 길이 제한이 없어 도메인 문구가 나간다.

    테스트 코드: IN-056
    """
    # when: JSON 스키마를 읽는다
    props = StorageSettingsRequest.model_json_schema()["properties"]["path"]

    # then: minLength·maxLength가 없다
    assert props["type"] == "string"
    assert "maxLength" not in props
    assert "minLength" not in props


def test_path_is_required() -> None:
    """path는 필수다.

    테스트 코드: IN-056
    """
    # when·then: path 없이 검증한다 → ValidationError다
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({})


@pytest.mark.parametrize("value", [None, 7, ["/data"], {"p": "/data"}])
def test_path_must_be_a_string(value: object) -> None:
    """path는 문자열만 받는다.

    테스트 코드: IN-056
    """
    # when·then: null·숫자·배열·객체로 검증한다 → ValidationError다
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({"path": value})


def test_unknown_fields_are_rejected() -> None:
    """모르는 필드는 거절한다.

    테스트 코드: IN-056
    """
    # when·then: 추가 필드가 든 본문을 검증한다 → ValidationError다
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({"path": "/data", "mode": "0777"})
