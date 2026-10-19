"""저장 위치 요청 스키마(P2b): 경로 형식·길이 판단은 도메인이 하고 스키마는 모양만 본다."""

import pytest
from pydantic import ValidationError

from app.web.schemas.storage import StorageSettingsRequest


def test_path_is_carried_as_given() -> None:
    request = StorageSettingsRequest.model_validate({"path": "  /data//files/ "})

    assert request.path == "  /data//files/ "


def test_an_overlong_path_is_left_to_the_domain_not_the_schema() -> None:
    request = StorageSettingsRequest.model_validate({"path": "/" + "a" * 5000})

    assert len(request.path) == 5001


def test_an_empty_path_is_left_to_the_domain_not_the_schema() -> None:
    assert StorageSettingsRequest.model_validate({"path": ""}).path == ""


def test_the_json_schema_has_no_length_constraint_so_the_domain_message_is_returned() -> None:
    props = StorageSettingsRequest.model_json_schema()["properties"]["path"]

    assert props["type"] == "string"
    assert "maxLength" not in props
    assert "minLength" not in props


def test_path_is_required() -> None:
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({})


@pytest.mark.parametrize("value", [None, 7, ["/data"], {"p": "/data"}])
def test_path_must_be_a_string(value: object) -> None:
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({"path": value})


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        StorageSettingsRequest.model_validate({"path": "/data", "mode": "0777"})
