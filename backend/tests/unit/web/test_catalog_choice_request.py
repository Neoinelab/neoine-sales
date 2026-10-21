"""CatalogChoiceRequest(AC-7·17): 요청의 선택 객체는 id 또는 name 중 정확히 하나다."""

import pytest
from pydantic import ValidationError

from app.application.choice import CatalogChoice
from app.web.schemas.choice import CatalogChoiceRequest
from tests.support.ids import MISSING_ID, new_id


def test_accepts_id_or_name() -> None:
    type_id = new_id()

    assert CatalogChoiceRequest(id=type_id).to_choice() == CatalogChoice(id=type_id)
    assert CatalogChoiceRequest(name="데모").to_choice() == CatalogChoice(name="데모")


def test_the_id_may_be_sent_as_a_json_integer() -> None:
    type_id = new_id()

    assert CatalogChoiceRequest.model_validate({"id": type_id}).to_choice().id == type_id


def test_the_largest_allowed_id_is_accepted() -> None:
    assert CatalogChoiceRequest.model_validate({"id": 2**53 - 1}).to_choice().id == 2**53 - 1


@pytest.mark.parametrize("bad", ["5", True, 5.0, 0, -3, 2**53])
def test_choice_id_must_be_a_json_integer(bad: object) -> None:
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"id": bad})


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"id": MISSING_ID, "name": "데모"}, id="both"),
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
        CatalogChoiceRequest.model_validate({"id": "not-an-id"})
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": 3})


def test_rejects_unknown_properties() -> None:
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": "데모", "label": "x"})


def test_an_empty_name_is_a_name_and_is_left_to_the_domain() -> None:
    assert CatalogChoiceRequest(name="").to_choice() == CatalogChoice(name="")
