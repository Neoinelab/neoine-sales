"""Feature: 파트너 미팅 기록을 항목별 조건(AND)으로 검색한다.

조건은 파트너·Deal(이름 또는 code)·미팅 날짜 시작/끝·미팅 내용·작성자다. 텍스트는 대소문자 무시 부분
일치이고 `%`·`_`·`\\`는 글자 그대로다. 미팅 날짜는 양끝을 포함한다. 시작이 끝보다 늦으면 422다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.partner_meetings import (
    DATE_RANGE_REVERSED,
    given_meeting,
    given_meeting_by,
    given_partner_deal,
    then_contents_are,
    then_page_is,
    when_list_meetings,
)
from tests.functional.steps.users import Session, given_signed_in_session, id_of

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def _given_three_meetings(
    api: Api,
) -> tuple[dict[str, Any], dict[str, Any], Session, Session]:
    """ERP(에이컴퍼니)·MES(비컴퍼니) Deal에 kim·park의 미팅 세 건. admin 로그인 상태로 끝난다."""
    await given_logged_in_as(api)
    erp = await given_partner_deal(api, name="ERP 구축", company="에이컴퍼니", contact="가나다")
    mes = await given_partner_deal(api, name="MES 도입", company="비컴퍼니", contact="라마바")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    await given_meeting_by(
        api, kim, erp["code"], company="에이컴퍼니", content="견적 전달", meeting_date="2027-03-01"
    )
    await given_meeting_by(
        api, park, erp["code"], company="에이컴퍼니", content="계약 논의", meeting_date="2027-03-10"
    )
    await given_meeting_by(
        api, kim, mes["code"], company="비컴퍼니", content="견적 재협상", meeting_date="2027-03-20"
    )
    return erp, mes, kim, park


async def test_the_content_filter_is_a_case_insensitive_substring(api: Api) -> None:
    """Scenario: 미팅 내용 일부로 찾는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    await given_meeting(api, deal["code"], content="Quote 전달", meeting_date="2027-03-01")
    await given_meeting(api, deal["code"], content="계약 논의", meeting_date="2027-03-02")
    # When
    response = await when_list_meetings(api, content="QUOTE")
    # Then
    then_contents_are(response, ["Quote 전달"])
    then_page_is(response, total=1, offset=0, limit=10)


async def test_the_partner_filter_matches_the_company_text(api: Api) -> None:
    """Scenario: 파트너 회사명 일부로 찾는다."""
    # Given
    await _given_three_meetings(api)
    # When
    response = await when_list_meetings(api, partner="에이컴")
    # Then
    then_contents_are(response, ["계약 논의", "견적 전달"])


async def test_the_deal_filter_matches_the_name_or_the_code(api: Api) -> None:
    """Scenario: Deal 이름 일부 또는 Deal code로 찾는다(대소문자 무시)."""
    # Given
    erp, mes, _kim, _park = await _given_three_meetings(api)
    # When
    by_name = await when_list_meetings(api, deal="mes")
    by_code = await when_list_meetings(api, deal=str(erp["code"]).lower())
    # Then
    then_contents_are(by_name, ["견적 재협상"])
    then_contents_are(by_code, ["계약 논의", "견적 전달"])
    assert mes["code"] != erp["code"]


async def test_the_author_filter_shows_only_that_users_records(api: Api) -> None:
    """Scenario: 작성자로 찾는다."""
    # Given
    await _given_three_meetings(api)
    park_id = await id_of(api, "park")
    # When
    response = await when_list_meetings(api, author_user_id=park_id)
    # Then
    then_contents_are(response, ["계약 논의"])


async def test_the_date_range_includes_both_ends(api: Api) -> None:
    """Scenario: 미팅 날짜 시작·끝은 양끝을 포함하고 한쪽만 줘도 된다."""
    # Given
    await _given_three_meetings(api)
    # When
    both = await when_list_meetings(api, date_from="2027-03-01", date_to="2027-03-10")
    only_from = await when_list_meetings(api, date_from="2027-03-10")
    only_to = await when_list_meetings(api, date_to="2027-03-01")
    # Then
    then_contents_are(both, ["계약 논의", "견적 전달"])
    then_contents_are(only_from, ["견적 재협상", "계약 논의"])
    then_contents_are(only_to, ["견적 전달"])


async def test_filters_are_anded(api: Api) -> None:
    """Scenario: 여러 조건을 함께 주면 모두 만족하는 기록만 나온다."""
    # Given
    await _given_three_meetings(api)
    kim_id = await id_of(api, "kim")
    # When
    response = await when_list_meetings(
        api, content="견적", partner="에이", author_user_id=kim_id, date_from="2027-03-01"
    )
    # Then
    then_contents_are(response, ["견적 전달"])
    then_page_is(response, total=1, offset=0, limit=10)


@pytest.mark.parametrize("special", ["%", "_", "\\"])
async def test_like_special_characters_are_searched_literally(api: Api, special: str) -> None:
    """Scenario: %, _, \\는 와일드카드가 아니라 글자 그대로 찾는다."""
    # Given
    await given_logged_in_as(api)
    deal = await given_partner_deal(api)
    await given_meeting(api, deal["code"], content=f"할인 10{special}", meeting_date="2027-03-01")
    await given_meeting(api, deal["code"], content="할인 100", meeting_date="2027-03-02")
    await given_meeting(api, deal["code"], content="할인 10X", meeting_date="2027-03-03")
    # When
    response = await when_list_meetings(api, content=f"10{special}")
    # Then
    then_contents_are(response, [f"할인 10{special}"])


async def test_blank_text_filters_are_ignored(api: Api) -> None:
    """Scenario: 공백뿐인 텍스트 조건은 조건이 없는 것과 같다."""
    # Given
    await _given_three_meetings(api)
    # When
    response = await when_list_meetings(api, content="   ", partner=" ", deal="")
    # Then
    then_page_is(response, total=3, offset=0, limit=10)


async def test_a_reversed_date_range_is_422_invalid_value(api: Api) -> None:
    """Scenario: 시작이 끝보다 늦으면 invalid-value 오류와 안내 문구다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_list_meetings(api, date_from="2027-03-10", date_to="2027-03-01")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == DATE_RANGE_REVERSED


async def test_a_search_date_outside_the_bounds_is_422_invalid_value(api: Api) -> None:
    """Scenario: 1900-01-01 이전 날짜 조건은 invalid-value 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_list_meetings(api, date_to="3000-01-01")
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")


@pytest.mark.parametrize(
    "params",
    [{"unknown": "x"}, {"content": "가" * 101}, {"partner": "가" * 201}, {"date_from": "10/01"}],
)
async def test_invalid_search_params_are_request_validation_errors(
    api: Api, params: dict[str, str]
) -> None:
    """Scenario: 모르는 파라미터·길이 초과·형식 오류는 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_list_meetings(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_a_search_with_no_match_is_an_empty_page(api: Api) -> None:
    """Scenario: 맞는 기록이 없으면 빈 목록이고 total 0이다."""
    # Given
    await _given_three_meetings(api)
    # When
    response = await when_list_meetings(api, content="없는 내용")
    # Then
    then_status_is(response, 200)
    then_page_is(response, total=0, offset=0, limit=10)
