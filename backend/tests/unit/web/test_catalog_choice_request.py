"""CatalogChoiceRequest(AC-7·17): 요청의 선택 객체는 id 또는 name 중 정확히 하나다."""

from uuid import uuid4

import pytest
from app.application.choice import CatalogChoice
from app.web.schemas.choice import CatalogChoiceRequest
from pydantic import ValidationError


def test_accepts_id_or_name() -> None:
    type_id = uuid4()

    assert CatalogChoiceRequest(id=type_id).to_choice() == CatalogChoice(id=type_id)
    assert CatalogChoiceRequest(name="데모").to_choice() == CatalogChoice(name="데모")


def test_the_id_may_be_sent_as_a_uuid_string() -> None:
    type_id = uuid4()

    assert CatalogChoiceRequest.model_validate({"id": str(type_id)}).to_choice().id == type_id


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"id": str(uuid4()), "name": "데모"}, id="both"),
        pytest.param({}, id="neither"),
        pytest.param({"id": None}, id="null-id"),
        pytest.param({"name": None}, id="null-name"),
    ],
)
def test_rejects_both_or_neither(body: dict[str, object]) -> None:
    with pytest.raises(ValidationError) as caught:
        CatalogChoiceRequest.model_validate(body)

    assert "id와 name 중 하나만 보내세요." in str(caught.value)


@pytest.mark.parametrize("value", ["meeting", "미팅", 3, None, ["x"]])
def test_rejects_plain_string(value: object) -> None:
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate(value)


def test_rejects_a_malformed_id_and_a_non_string_name() -> None:
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"id": "not-a-uuid"})
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": 3})


def test_rejects_unknown_properties() -> None:
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": "데모", "label": "x"})


def test_an_empty_name_is_a_name_and_is_left_to_the_domain() -> None:
    assert CatalogChoiceRequest(name="").to_choice() == CatalogChoice(name="")
