"""Feature: Deal의 BANT는 목록에서 고르거나 이름으로 입력하고, 없는 이름은 새 Label이 된다.

구분(budget·authority·need·timeline)마다 `{"id": ...}`(그 구분의 Label), `{"name": ...}`(같은
구분에서 대소문자 무시로 찾고, 없으면 같은 요청에서 만든다), null(선택 안 함) 중 하나를 보낸다.
등록·수정이 실패하면 새 Label도 생기지 않는다. 응답 Deal의 bant 형식(구분별 Label id)은 그대로다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import (
    deal_body,
    given_deal,
    given_label_id,
    given_my_user_id,
    then_deal_count_is,
    when_register_deal,
    when_register_deal_with_body,
    when_update_deal_with_body,
)
from tests.functional.steps.labels import given_label_list, then_label_count_is
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NONE = {"budget": None, "authority": None, "need": None, "timeline": None}
LABEL_INVALID = "BANT Label이 올바르지 않습니다."
LABEL_REQUIRED = "Label 이름을 입력하세요."
LABEL_TOO_LONG = "Label 이름은 50자 이내로 입력하세요."
DEFAULT_LABELS = 23


async def _labels_named(api: Api, name: str) -> list[dict[str, object]]:
    return [x for x in await given_label_list(api) if x["name"] == name]


async def test_registering_a_deal_with_a_new_bant_name_creates_the_label(api: Api) -> None:
    """Scenario: 목록에 없는 BANT 이름은 같은 요청에서 그 구분의 새 Label이 되고 Deal이 가리킨다."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    # When
    response = await when_register_deal(
        api, bant={**NONE, "authority": {"name": "  신규 결재선  "}}
    )
    # Then
    then_status_is(response, 201)
    (created,) = await _labels_named(api, "신규 결재선")
    assert (created["category"], created["is_default"], created["usage_count"]) == (
        "authority",
        False,
        1,
    )
    assert created["created_by"]["id"] == me  # type: ignore[index]
    assert response.json()["bant"] == {**NONE, "authority": created["id"]}
    await then_label_count_is(api, count=DEFAULT_LABELS + 1)


async def test_existing_label_name_is_reused_ignoring_case(api: Api) -> None:
    """Scenario: 같은 구분의 기존 Label과 대소문자만 다른 이름은 그 Label을 쓴다."""
    # Given
    await given_logged_in_as(api, role="sales")
    ceo = await given_label_id(api, category="authority", name="CEO 보고 완료")
    # When
    response = await when_register_deal(api, bant={**NONE, "authority": {"name": "ceo 보고 완료"}})
    # Then
    then_status_is(response, 201)
    assert response.json()["bant"] == {**NONE, "authority": ceo}
    await then_label_count_is(api, count=DEFAULT_LABELS)


async def test_the_same_name_in_another_category_creates_a_new_label(api: Api) -> None:
    """Scenario: '모름'은 authority·need에 있어도 budget에는 없으므로 budget에 새로 만든다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, bant={**NONE, "budget": {"name": "모름"}})
    # Then
    then_status_is(response, 201)
    labels = await _labels_named(api, "모름")
    assert sorted(str(x["category"]) for x in labels) == ["authority", "budget", "need"]
    budget = next(x for x in labels if x["category"] == "budget")
    assert response.json()["bant"] == {**NONE, "budget": budget["id"]}


async def test_an_id_object_and_null_are_accepted_per_category(api: Api) -> None:
    """Scenario: 구분마다 {id}, {name}, null을 섞어 보내도 각각 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    # When
    response = await when_register_deal(
        api,
        bant={"budget": {"id": budget}, "authority": None, "need": {"name": "신규 필요"}},
    )
    # Then
    then_status_is(response, 201)
    bant = response.json()["bant"]
    assert (bant["budget"], bant["authority"], bant["timeline"]) == (budget, None, None)
    (need,) = await _labels_named(api, "신규 필요")
    assert bant["need"] == need["id"]


async def test_a_bant_category_left_out_means_not_selected(api: Api) -> None:
    """Scenario: bant에서 빠진 구분은 선택 안 함(null)이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, bant={})
    # Then
    then_status_is(response, 201)
    assert response.json()["bant"] == NONE


async def test_failed_registration_leaves_no_new_label(api: Api) -> None:
    """Scenario: BANT 뒤의 검증(구매절차)이 실패하면 Deal도 새 Label도 생기지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(
        api, bant={**NONE, "need": {"name": "신규 필요"}}, procurement="가" * 501
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_label_count_is(api, count=DEFAULT_LABELS)
    await then_deal_count_is(api, 0)


async def test_a_contact_error_after_bant_leaves_no_new_label(api: Api) -> None:
    """Scenario: 연락처 형식 오류로 실패해도 새 Label은 생기지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    body = await deal_body(api, bant={**NONE, "need": {"name": "신규 필요"}})
    body["customer"] = {**body["customer"], "email": "bad"}
    # When
    response = await when_register_deal_with_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_label_count_is(api, count=DEFAULT_LABELS)


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("   ", LABEL_REQUIRED, id="blank"),
        pytest.param("가" * 51, LABEL_TOO_LONG, id="51-chars"),
    ],
)
async def test_blank_or_long_bant_name_is_rejected_with_the_label_message(
    api: Api, name: str, message: str
) -> None:
    """Scenario: 공백뿐이거나 51자인 BANT 이름은 Label 이름 규칙 문구로 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_register_deal(api, bant={**NONE, "need": {"name": name}})
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == message
    await then_label_count_is(api, count=DEFAULT_LABELS)


async def test_a_50_character_bant_name_is_accepted_and_a_nul_is_rejected(api: Api) -> None:
    """Scenario: 50자 이름은 통과하고 NUL이 든 이름은 서버 오류 없이 422다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    accepted = await when_register_deal(api, bant={**NONE, "need": {"name": "가" * 50}})
    rejected = await when_register_deal(api, bant={**NONE, "need": {"name": "신\x00규"}})
    # Then
    then_status_is(accepted, 201)
    then_problem_is(rejected, status=422, type_suffix="invalid-value")


async def test_bant_is_validated_after_sync_and_before_procurement(api: Api) -> None:
    """Scenario: 검증 순서는 Status·Forecast 동기화 다음 BANT, 그 다음 구매절차다."""
    # Given
    await given_logged_in_as(api, role="sales")
    bad_bant = {**NONE, "need": {"name": "   "}}
    # When
    sync = await when_register_deal(
        api, bant=bad_bant, status_key="contract_completed", forecast_key="pipeline"
    )
    label = await when_register_deal(api, bant=bad_bant, procurement="가" * 501)
    # Then
    assert sync.json()["detail"] == "Status와 Forecast의 동기화가 맞지 않습니다."
    assert label.json()["detail"] == LABEL_REQUIRED


@pytest.mark.parametrize("category", ["budget", "authority"])
async def test_an_id_of_another_category_or_unknown_is_rejected(api: Api, category: str) -> None:
    """Scenario: 다른 구분의 Label id나 없는 id는 422(BANT Label이 올바르지 않습니다)다."""
    # Given
    await given_logged_in_as(api, role="sales")
    need = await given_label_id(api, category="need", name="모름")
    unknown = MISSING_ID
    # When
    other = await when_register_deal(api, bant={**NONE, category: {"id": need}})
    missing = await when_register_deal(api, bant={**NONE, category: {"id": unknown}})
    # Then
    for response in (other, missing):
        then_problem_is(response, status=422, type_suffix="invalid-value")
        assert response.json()["detail"] == LABEL_INVALID
    await then_deal_count_is(api, 0)


async def test_old_bare_bant_id_is_rejected(api: Api) -> None:
    """Scenario: 구 형식(Label id 값 그대로)은 422 request-validation이고 Deal은 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    budget = await given_label_id(api, category="budget", name="풀 예산 확보")
    body = await deal_body(api)
    body["bant"] = {**NONE, "budget": budget}
    # When
    response = await when_register_deal_with_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_deal_count_is(api, 0)


@pytest.mark.parametrize(
    "choice",
    [
        pytest.param({}, id="neither"),
        pytest.param({"id": MISSING_ID, "name": "x"}, id="both"),
        pytest.param("풀 예산 확보", id="plain-name-string"),
        pytest.param({"id": "not-an-id"}, id="id-not-an-id"),
    ],
)
async def test_a_malformed_bant_choice_is_a_request_validation_error(
    api: Api, choice: object
) -> None:
    """Scenario: id·name이 둘 다/하나도 없거나 문자열인 BANT 값은 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = await deal_body(api)
    body["bant"] = {**NONE, "budget": choice}
    # When
    registered = await when_register_deal_with_body(api, body)
    patched = await when_update_deal_with_body(api, deal["code"], {"bant": body["bant"]})
    # Then
    then_problem_is(registered, status=422, type_suffix="request-validation")
    then_problem_is(patched, status=422, type_suffix="request-validation")
