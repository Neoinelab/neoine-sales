"""CatalogChoiceRequest: 요청의 선택 객체는 id 또는 name 중 정확히 하나다."""

from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from app.application.choice import CatalogChoice
from app.web.schemas.choice import CatalogChoiceRequest
from app.web.schemas.deal import DealCreateRequest, DealPatchRequest
from app.web.schemas.deal_action import DealActionCreateRequest, DealActionUpdateRequest
from tests.support.ids import MISSING_ID, new_id
from tests.support.user_ids import OWNER_ID

if TYPE_CHECKING:
    from collections.abc import Callable

_DEAL_BODY = {
    "name": "ERP 구축",
    "owner_user_id": OWNER_ID,
    "solution": "ITDR",
    "users": 10,
    "status_key": "prospecting",
    "forecast_key": "pipeline",
    "revenue_amount": 150_000_000,
    "revenue_date": "2026-06-30",
    "customer": {"company": "네오인", "name": "김철수"},
}

# 선택 객체를 받는 네 요청: Deal 등록·수정의 bant.<구분>, Action 등록·수정의 action_type
HOLDERS: dict[str, Callable[[Any], object]] = {
    "deal-create": lambda c: DealCreateRequest.model_validate({**_DEAL_BODY, "bant": {"need": c}}),
    "deal-patch": lambda c: DealPatchRequest.model_validate({"bant": {"need": c}}),
    "action-create": lambda c: DealActionCreateRequest.model_validate(
        {"action_type": c, "action": "x"}
    ),
    "action-update": lambda c: DealActionUpdateRequest.model_validate(
        {"action_type": c, "action": "x"}
    ),
}


def test_accepts_id_or_name() -> None:
    """선택 요청은 id만 또는 name만 담으면 받아들인다.

    테스트 코드: CL-063
    """
    type_id = new_id()

    # when: id만, name만 담은 요청을 해석한다
    assert CatalogChoiceRequest(id=type_id).to_choice() == CatalogChoice(id=type_id)
    # then: 각각 id 선택, name 선택으로 바뀐다
    assert CatalogChoiceRequest(name="데모").to_choice() == CatalogChoice(name="데모")


def test_the_id_may_be_sent_as_a_json_integer() -> None:
    """선택 id는 JSON 정수로 받는다.

    테스트 코드: CL-064
    """
    type_id = new_id()

    # when: 정수 id를 담아 해석한다
    actual = CatalogChoiceRequest.model_validate({"id": type_id}).to_choice().id
    # then: 그 id 선택이 된다
    assert actual == type_id


def test_the_largest_allowed_id_is_accepted() -> None:
    """범위의 상한(2^53-1)인 id도 받는다.

    테스트 코드: CL-064
    """
    # when: 2^53-1 id를 해석한다
    actual = CatalogChoiceRequest.model_validate({"id": 2**53 - 1}).to_choice().id
    # then: 그 id 선택이 된다
    assert actual == 2**53 - 1


@pytest.mark.parametrize("bad", ["5", True, 5.0, 0, -3, 2**53])
def test_choice_id_must_be_a_json_integer(bad: object) -> None:
    """문자열·불리언·실수·범위 밖 id는 거절한다.

    테스트 코드: CL-064
    """
    # when·then: 정수가 아니거나 범위 밖인 id를 해석한다 → 검증 오류다
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
    """id와 name을 둘 다 보내거나 둘 다 없으면 거절한다.

    테스트 코드: CL-063
    """
    # when: 둘 다 있거나 둘 다 없는(null 포함) 요청을 해석한다
    with pytest.raises(ValidationError) as caught:
        CatalogChoiceRequest.model_validate(body)

    # then: 'id와 name 중 하나만 보내세요.' 검증 오류다
    assert "id와 name 중 하나만 보내세요." in str(caught.value)


@pytest.mark.parametrize("value", ["meeting", "미팅", 3, None, ["x"]])
def test_rejects_plain_string(value: object) -> None:
    """객체가 아닌 값(문자열·정수·null·배열)은 거절한다.

    테스트 코드: CL-063
    """
    # when·then: 객체가 아닌 값을 해석한다 → 검증 오류다
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate(value)


def test_rejects_a_malformed_id_and_a_non_string_name() -> None:
    """형식이 틀린 id나 문자열이 아닌 name은 거절한다.

    테스트 코드: CL-063, CL-064
    """
    # when·then: id가 'not-an-id'이거나 name이 정수인 요청을 해석한다 → 둘 다 검증 오류다
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"id": "not-an-id"})
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": 3})


def test_rejects_unknown_properties() -> None:
    """모르는 키가 든 선택 객체는 거절한다.

    테스트 코드: CL-063
    """
    # when·then: 모르는 키가 있는 요청을 해석한다 → 검증 오류다
    with pytest.raises(ValidationError):
        CatalogChoiceRequest.model_validate({"name": "데모", "label": "x"})


def test_an_empty_name_is_a_name_and_is_left_to_the_domain() -> None:
    """빈 문자열 name도 이름으로 받고 이름 규칙은 도메인이 판정한다.

    테스트 코드: CL-065
    """
    # when: 빈 name을 해석한다
    actual = CatalogChoiceRequest(name="").to_choice()
    # then: name이 빈 문자열인 선택이 된다
    assert actual == CatalogChoice(name="")


@pytest.mark.parametrize("holder", list(HOLDERS))
@pytest.mark.parametrize(
    "bad",
    [
        {"id": MISSING_ID, "name": "데모"},
        {},
        "데모",
        5,
        {"id": "5"},
        {"name": 3},
        {"name": "x", "k": 1},
    ],
    ids=["both", "neither", "string", "integer", "string-id", "non-string-name", "unknown-key"],
)
def test_every_request_that_takes_a_choice_rejects_a_malformed_one(
    holder: str, bad: object
) -> None:
    """Deal 등록·수정과 Action 등록·수정 요청은 모두 같은 선택 형식 위반을 거절한다.

    테스트 코드: CL-063
    """
    # when·then: 형식이 틀린 선택 객체를 담아 요청을 해석한다
    #   → 검증 오류(HTTP로는 422 request-validation)다
    with pytest.raises(ValidationError):
        HOLDERS[holder](bad)


@pytest.mark.parametrize("holder", list(HOLDERS))
@pytest.mark.parametrize("good", [{"id": 7}, {"name": "데모"}], ids=["id", "name"])
def test_every_request_that_takes_a_choice_accepts_an_id_or_a_name(
    holder: str, good: object
) -> None:
    """네 요청 모두 id 또는 name 하나만 담은 선택 객체를 받는다.

    테스트 코드: CL-063
    """
    # when: id 또는 name 하나만 담은 선택 객체로 요청을 해석한다
    request = HOLDERS[holder](good)

    # then: 요청이 만들어진다
    assert request is not None
