"""Feature: sales·admin은 파트너 회사별 미팅을 여러 건 한꺼번에 입력한다.

미팅은 Deal과 무관하다. 파트너 회사는 파트너 연락처에 등록된 회사 목록에서 고르고(대소문자 무시,
대표 표기로 저장), 어느 Deal에도 연결되지 않은 회사도 입력된다. 일괄 입력은 한 트랜잭션이고 위반은
모두 모아 위치(`items[i].필드`)와 함께 422 invalid-value로 돌려준다. 미래 날짜는 받는다. 읽기
전용(user)은 입력할 수 없다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.partner_meetings import (
    COMPANY_NOT_FOUND,
    CONTENT_REQUIRED,
    HANBIT,
    OUT_OF_BOUNDS,
    READ_ONLY,
    contents_of,
    given_partner,
    meeting_item,
    then_all_contents_are,
    then_errors_are,
    then_meeting_has_the_documented_fields,
    when_register_meetings,
    when_register_meetings_as,
    when_register_with_body,
)
from tests.functional.steps.users import given_signed_in_session, id_of

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_sales_records_a_meeting_with_a_partner_that_has_no_deal(api: Api) -> None:
    """Scenario: Deal이 하나도 없어도 등록된 파트너 회사로 미팅을 입력할 수 있다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    # When
    response = await when_register_meetings_as(api, kim, [meeting_item(content="첫 만남")])
    # Then
    then_status_is(response, 201)
    (saved,) = response.json()["items"]
    then_meeting_has_the_documented_fields(saved)
    assert "deal" not in saved
    assert saved["partner_company"] == HANBIT
    assert saved["author"]["id"] == await id_of(api, "kim")
    await then_all_contents_are(api, ["첫 만남"])


async def test_sales_registers_several_meetings_in_one_request(api: Api) -> None:
    """Scenario: sales가 세 건을 한 번에 입력하면 입력 순서대로 저장된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_partner(api, company="비컴퍼니", contact="라마바")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    items = [
        meeting_item(content="첫째", meeting_date="2027-03-03"),
        meeting_item(content="둘째", meeting_date="2027-03-02", company="비컴퍼니"),
        meeting_item(content="셋째", meeting_date="2027-03-01"),
    ]
    # When
    response = await when_register_meetings_as(api, kim, items)
    # Then
    then_status_is(response, 201)
    assert "location" not in response.headers
    saved = response.json()["items"]
    assert [i["content"] for i in saved] == ["첫째", "둘째", "셋째"]
    assert [i["partner_company"] for i in saved] == [HANBIT, "비컴퍼니", HANBIT]
    await then_all_contents_are(api, ["첫째", "둘째", "셋째"])


async def test_admin_registers_too_and_content_is_trimmed(api: Api) -> None:
    """Scenario: admin도 입력할 수 있고 내용의 앞뒤 공백은 지워지며 가운데 줄바꿈은 남는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    response = await when_register_meetings(
        api, [meeting_item(content="\n 계약 논의\n다음 주 방문 \n")]
    )
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["content"] == "계약 논의\n다음 주 방문"


async def test_a_future_meeting_date_is_accepted(api: Api) -> None:
    """Scenario: 미팅 날짜는 미래여도 받는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    response = await when_register_meetings(api, [meeting_item(meeting_date="2999-12-31")])
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["meeting_date"] == "2999-12-31"


async def test_the_company_spelling_is_normalized_to_the_registered_one(api: Api) -> None:
    """Scenario: 대소문자가 다른 회사명을 입력해도 등록된 대표 표기로 저장된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api, company="HanbitCo", contact="가나다")
    # When
    response = await when_register_meetings(api, [meeting_item(company="hanbitco")])
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["partner_company"] == "HanbitCo"


async def test_a_batch_with_deal_code_is_rejected_and_nothing_is_saved(api: Api) -> None:
    """Scenario: 항목에 deal_code가 있으면 request-validation 오류이고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    items = [meeting_item(), {**meeting_item(), "deal_code": "20261016-A001"}]
    # When
    response = await when_register_meetings(api, items)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_all_contents_are(api, [])


async def test_an_unknown_company_row_rejects_the_whole_batch(api: Api) -> None:
    """Scenario: 일부 행이 틀리면 아무것도 저장되지 않고 모든 위반이 위치와 함께 돌아온다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    items = [
        meeting_item(),
        meeting_item(company="없는회사"),
        meeting_item(content="  "),
        meeting_item(meeting_date="3000-01-01"),
    ]
    # When
    response = await when_register_meetings(api, items)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == COMPANY_NOT_FOUND
    then_errors_are(
        response,
        [
            (("items", 1, "partner_company"), COMPANY_NOT_FOUND),
            (("items", 2, "content"), CONTENT_REQUIRED),
            (("items", 3, "meeting_date"), OUT_OF_BOUNDS),
        ],
    )
    await then_all_contents_are(api, [])


@pytest.mark.parametrize("day", ["1899-12-31", "3000-01-01"])
async def test_a_meeting_date_outside_the_bounds_is_located_at_the_date(api: Api, day: str) -> None:
    """Scenario: 1900-01-01~2999-12-31 밖의 미팅 날짜는 그 칸 위치로 거절된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    response = await when_register_meetings(api, [meeting_item(meeting_date=day)])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_errors_are(response, [(("items", 0, "meeting_date"), OUT_OF_BOUNDS)])


async def test_nul_in_the_content_is_rejected_at_the_content(api: Api) -> None:
    """Scenario: NUL 문자가 든 내용은 content 위치로 거절된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    response = await when_register_meetings(api, [meeting_item(content="a\x00b")])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["errors"][0]["location"] == ["items", 0, "content"]


async def test_a_very_long_multiline_content_is_stored_whole(api: Api) -> None:
    """Scenario: 내용에는 길이 제한이 없어 긴 여러 줄도 그대로 저장된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    text = "\n".join(f"줄 {number} 😀" for number in range(5_000))
    # When
    response = await when_register_meetings(api, [meeting_item(content=text)])
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["content"] == text


async def test_fifty_items_are_accepted_and_fifty_one_are_not(api: Api) -> None:
    """Scenario: 한 번에 50건까지 받고 51건은 request-validation 오류이며 하나도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    too_many = await when_register_meetings(api, [meeting_item()] * 51)
    fifty = await when_register_meetings(api, [meeting_item()] * 50)
    # Then
    then_problem_is(too_many, status=422, type_suffix="request-validation")
    then_status_is(fifty, 201)
    assert len(contents_of(fifty)) == 50


@pytest.mark.parametrize(
    "body",
    [{"items": []}, {}, {"items": [{"partner_company": HANBIT}]}, {"items": "x"}],
)
async def test_malformed_requests_are_request_validation_errors(api: Api, body: object) -> None:
    """Scenario: 빈 목록·누락·잘못된 형식은 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_register_with_body(api, body)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_read_only_user_cannot_register(api: Api) -> None:
    """Scenario: 읽기 전용 사용자는 403 읽기 전용 문구를 받고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_register_meetings_as(api, viewer, [meeting_item()])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == READ_ONLY
    await then_all_contents_are(api, [])
