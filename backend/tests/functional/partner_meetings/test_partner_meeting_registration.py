"""Feature: sales·admin은 파트너 회사별로 그 회사와 연결된 Deal의 미팅을 여러 건 한꺼번에 입력한다.

Deal 선택지는 회사 담당자 누구든 지금 활성 파트너로 연결된 Deal이다(Won·Lost 포함). 일괄 입력은 한
트랜잭션이고 위반은 모두 모아 위치(`items[i].필드`)와 함께 422 invalid-value로 돌려준다. 미래 날짜는
받는다. 읽기 전용(user)은 입력할 수 없다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deals import partner_draft, when_update_deal
from tests.functional.steps.partner_meetings import (
    COMPANY_NOT_FOUND,
    CONTENT_REQUIRED,
    DEAL_NOT_FOUND,
    DEAL_NOT_LINKED,
    HANBIT,
    OUT_OF_BOUNDS,
    READ_ONLY,
    contents_of,
    given_partner_deal,
    meeting_item,
    then_all_contents_are,
    then_errors_are,
    then_meeting_has_the_documented_fields,
    when_get_deal_options,
    when_register_meetings,
    when_register_meetings_as,
    when_register_with_body,
)
from tests.functional.steps.users import given_signed_in_session, id_of

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_sales_registers_several_meetings_across_deals_in_one_request(api: Api) -> None:
    """Scenario: sales가 같은 회사의 Deal 둘에 세 건을 한 번에 입력하면 입력 순서대로 저장된다."""
    # Given
    await given_logged_in_as(api)
    erp = await given_partner_deal(api, name="ERP", contact="가나다")
    mes = await given_partner_deal(api, name="MES", contact="라마바")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    items = [
        meeting_item(erp["code"], content="첫째", meeting_date="2027-03-03"),
        meeting_item(mes["code"], content="둘째", meeting_date="2027-03-02"),
        meeting_item(erp["code"], content="셋째", meeting_date="2027-03-01"),
    ]
    # When
    response = await when_register_meetings_as(api, kim, items)
    # Then
    then_status_is(response, 201)
    assert "location" not in response.headers
    saved = response.json()["items"]
    assert [i["content"] for i in saved] == ["첫째", "둘째", "셋째"]
    assert [i["deal"]["name"] for i in saved] == ["ERP", "MES", "ERP"]
    for entry in saved:
        then_meeting_has_the_documented_fields(entry)
        assert entry["author"]["id"] == await id_of(api, "kim")
        assert entry["partner_company"] == HANBIT
    await then_all_contents_are(api, ["첫째", "둘째", "셋째"])


async def test_admin_registers_too_and_content_is_trimmed(api: Api) -> None:
    """Scenario: admin도 입력할 수 있고 내용의 앞뒤 공백은 지워지며 가운데 줄바꿈은 남는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    response = await when_register_meetings(
        api, [meeting_item(deal["code"], content="\n 계약 논의\n다음 주 방문 \n")]
    )
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["content"] == "계약 논의\n다음 주 방문"


async def test_a_future_meeting_date_is_accepted(api: Api) -> None:
    """Scenario: 미팅 날짜는 미래여도 받는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    response = await when_register_meetings(
        api, [meeting_item(deal["code"], meeting_date="2999-12-31")]
    )
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["meeting_date"] == "2999-12-31"


async def test_deals_of_every_contact_of_the_company_are_selectable(api: Api) -> None:
    """Scenario: 같은 회사 다른 담당자로 연결된 Deal 둘이 모두 선택지에 있고 입력된다."""
    # Given
    await given_logged_in_as(api)
    first = await given_partner_deal(api, name="B 프로젝트", contact="가나다")
    second = await given_partner_deal(api, name="A 프로젝트", contact="라마바")
    await given_partner_deal(api, name="타사", company="다른파트너", contact="사아자")
    # When
    options = await when_get_deal_options(api, HANBIT)
    saved = await when_register_meetings(
        api, [meeting_item(first["code"]), meeting_item(second["code"])]
    )
    # Then
    then_status_is(options, 200)
    assert [o["name"] for o in options.json()["items"]] == ["A 프로젝트", "B 프로젝트"]
    assert set(options.json()["items"][0]) == {"code", "name", "customer_company"}
    assert options.json()["items"][0]["customer_company"] == "네오인"
    then_status_is(saved, 201)


async def test_won_and_lost_deals_are_selectable_and_accepted(api: Api) -> None:
    """Scenario: Won·Lost Deal도 선택지에 있고 미팅을 입력할 수 있다."""
    # Given
    await given_logged_in_as(api)
    won = await given_partner_deal(api, name="수주", forecast="won")
    lost = await given_partner_deal(api, name="실주", forecast="lost")
    # When
    options = await when_get_deal_options(api, HANBIT)
    saved = await when_register_meetings(
        api, [meeting_item(won["code"]), meeting_item(lost["code"])]
    )
    # Then
    assert {o["code"] for o in options.json()["items"]} == {won["code"], lost["code"]}
    then_status_is(saved, 201)


async def test_deal_options_of_an_unknown_company_is_an_empty_list(api: Api) -> None:
    """Scenario: 등록되지 않은 회사의 Deal 선택지는 200과 빈 목록이다."""
    # Given
    await given_logged_in_as(api)
    await given_partner_deal(api)
    # When
    response = await when_get_deal_options(api, "없는회사")
    # Then
    then_status_is(response, 200)
    assert response.json() == {"items": []}


async def test_the_company_spelling_is_normalized_to_the_registered_one(api: Api) -> None:
    """Scenario: 대소문자가 다른 회사명을 입력해도 등록된 대표 표기로 저장된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api, company="HanbitCo", contact="가나다")
    # When
    response = await when_register_meetings(api, [meeting_item(deal["code"], company="hanbitco")])
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["partner_company"] == "HanbitCo"
    options = await when_get_deal_options(api, "HANBITCO")
    assert [o["code"] for o in options.json()["items"]] == [deal["code"]]


async def test_one_invalid_row_saves_nothing_and_every_violation_is_located(api: Api) -> None:
    """Scenario: 일부 행이 틀리면 아무것도 저장되지 않고 모든 위반이 위치와 함께 돌아온다."""
    # Given
    await given_logged_in_as(api)
    mine = await given_partner_deal(api, name="내 Deal")
    other = await given_partner_deal(api, name="타사", company="다른파트너", contact="사아자")
    items = [
        meeting_item(mine["code"]),
        meeting_item(mine["code"], company="없는회사"),
        meeting_item(other["code"], company=HANBIT, content="  "),
        meeting_item(mine["code"]),
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
            (("items", 2, "deal_code"), DEAL_NOT_LINKED),
            (("items", 2, "content"), CONTENT_REQUIRED),
        ],
    )
    await then_all_contents_are(api, [])


@pytest.mark.parametrize("code", ["20260101-ZZZZ", "not-a-code"])
async def test_a_missing_deal_and_a_malformed_code_get_the_same_message(
    api: Api, code: str
) -> None:
    """Scenario: 없는 Deal code와 형식이 틀린 code는 같은 문구로 거절된다."""
    # Given
    await given_logged_in_as(api)
    await given_partner_deal(api)
    # When
    response = await when_register_meetings(api, [meeting_item(code)])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_errors_are(response, [(("items", 0, "deal_code"), DEAL_NOT_FOUND)])


async def test_a_partner_that_was_unlinked_from_the_deal_is_rejected(api: Api) -> None:
    """Scenario: 파트너를 바꾼 Deal에는 이전 파트너 이름으로 입력할 수 없고 새 파트너로는 된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api, company="옛파트너", contact="가나다")
    changed = await when_update_deal(
        api,
        deal["code"],
        partner=partner_draft(company="새파트너", name="라마바", email="n@p.test"),
    )
    then_status_is(changed, 200)
    # When
    rejected = await when_register_meetings(api, [meeting_item(deal["code"], company="옛파트너")])
    accepted = await when_register_meetings(api, [meeting_item(deal["code"], company="새파트너")])
    # Then
    then_problem_is(rejected, status=422, type_suffix="invalid-value")
    then_errors_are(rejected, [(("items", 0, "deal_code"), DEAL_NOT_LINKED)])
    then_status_is(accepted, 201)
    options = await when_get_deal_options(api, "옛파트너")
    assert options.json() == {"items": []}


async def test_a_deal_whose_partner_was_removed_is_not_selectable(api: Api) -> None:
    """Scenario: 파트너를 제거한 Deal은 그 회사의 선택지에서 빠지고 입력도 거절된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    await when_update_deal(api, deal["code"], partner=None)
    # When
    options = await when_get_deal_options(api, HANBIT)
    rejected = await when_register_meetings(api, [meeting_item(deal["code"])])
    # Then
    assert options.json() == {"items": []}
    then_problem_is(rejected, status=422, type_suffix="invalid-value")


@pytest.mark.parametrize(
    ("day", "message"),
    [("1899-12-31", OUT_OF_BOUNDS), ("3000-01-01", OUT_OF_BOUNDS)],
)
async def test_a_meeting_date_outside_the_bounds_is_located_at_the_date(
    api: Api, day: str, message: str
) -> None:
    """Scenario: 1900-01-01~2999-12-31 밖의 미팅 날짜는 그 칸 위치로 거절된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    response = await when_register_meetings(api, [meeting_item(deal["code"], meeting_date=day)])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    then_errors_are(response, [(("items", 0, "meeting_date"), message)])


async def test_nul_in_the_content_is_rejected_at_the_content(api: Api) -> None:
    """Scenario: NUL 문자가 든 내용은 content 위치로 거절된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    response = await when_register_meetings(api, [meeting_item(deal["code"], content="a\x00b")])
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["errors"][0]["location"] == ["items", 0, "content"]


async def test_a_very_long_multiline_content_is_stored_whole(api: Api) -> None:
    """Scenario: 내용에는 길이 제한이 없어 긴 여러 줄도 그대로 저장된다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    text = "\n".join(f"줄 {number} 😀" for number in range(5_000))
    # When
    response = await when_register_meetings(api, [meeting_item(deal["code"], content=text)])
    # Then
    then_status_is(response, 201)
    assert response.json()["items"][0]["content"] == text


async def test_fifty_items_are_accepted_and_fifty_one_are_not(api: Api) -> None:
    """Scenario: 한 번에 50건까지 받고 51건은 request-validation 오류이며 하나도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    # When
    too_many = await when_register_meetings(api, [meeting_item(deal["code"])] * 51)
    fifty = await when_register_meetings(api, [meeting_item(deal["code"])] * 50)
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
    deal = await given_partner_deal(api)
    viewer = await given_signed_in_session(api, login_id="viewer", role="user")
    # When
    response = await when_register_meetings_as(api, viewer, [meeting_item(deal["code"])])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == READ_ONLY
    await then_all_contents_are(api, [])
