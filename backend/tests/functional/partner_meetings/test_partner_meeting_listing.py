"""Feature: 로그인한 모든 사용자는 파트너 미팅 기록을 최신 미팅 날짜순으로 10건씩 이어서 본다.

미팅은 Deal과 무관하다. 기본 정렬은 미팅 날짜 내림차순(같은 날짜는 나중 등록 먼저)이고,
열 4개(파트너·미팅 날짜·
미팅 내용·작성자)로 정렬을 바꿀 수 있다. 텍스트 열 정렬의 동률은 방향과 무관하게
미팅 날짜 내림차순 ->
나중 등록 먼저다. 페이지는 offset/limit이고 응답에 전체 건수가 있다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.partner_meetings import (
    HANBIT,
    contents_of,
    given_many_meetings,
    given_meeting,
    given_meeting_by,
    given_partner,
    then_contents_are,
    then_meeting_has_the_documented_fields,
    then_page_is,
    when_get_deal_options,
    when_list_meetings,
)
from tests.functional.steps.users import given_signed_in_session

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NAMES = [f"기록 {number:02d}" for number in range(12)]


async def test_the_default_list_shows_the_ten_newest_meetings(api: Api) -> None:
    """Scenario: 12건 중 미팅 날짜가 가장 늦은 10건이 먼저 보이고 전체 건수가 12다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_many_meetings(api, 12)
    # When
    response = await when_list_meetings(api)
    # Then
    then_status_is(response, 200)
    then_contents_are(response, list(reversed(NAMES))[:10])
    then_page_is(response, total=12, offset=0, limit=10)


async def test_the_next_page_continues_without_overlap(api: Api) -> None:
    """Scenario: offset=10으로 다음 10건을 받으면 나머지 2건이 이어지고 끝을 넘으면 비어 있다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_many_meetings(api, 12)
    first = await when_list_meetings(api)
    # When
    second = await when_list_meetings(api, offset=10)
    beyond = await when_list_meetings(api, offset=20)
    # Then
    assert contents_of(second) == ["기록 01", "기록 00"]
    assert not set(contents_of(first)) & set(contents_of(second))
    then_page_is(second, total=12, offset=10, limit=10)
    assert contents_of(beyond) == []
    then_page_is(beyond, total=12, offset=20, limit=10)


async def test_meetings_on_the_same_day_show_the_later_registered_first(api: Api) -> None:
    """Scenario: 같은 미팅 날짜는 나중에 등록한 기록이 먼저 나온다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    for content in ("먼저 등록", "나중 등록"):
        await given_meeting(api, content=content, meeting_date="2027-03-05")
    await given_meeting(api, content="더 늦은 날짜", meeting_date="2027-03-06")
    # When
    response = await when_list_meetings(api)
    # Then
    then_contents_are(response, ["더 늦은 날짜", "나중 등록", "먼저 등록"])


async def test_a_listed_meeting_has_the_documented_fields(api: Api) -> None:
    """Scenario: 목록 항목은 파트너 회사·작성자·서버 오프셋 시각을 담고 deal 키는 없다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    saved = await given_meeting_by(api, kim, content="계약 논의\n다음 주")
    # When
    response = await when_list_meetings(api)
    # Then
    (listed,) = response.json()["items"]
    then_meeting_has_the_documented_fields(listed)
    assert "deal" not in listed
    assert listed["id"] == saved["id"]
    assert listed["partner_company"] == HANBIT
    assert listed["meeting_date"] == "2027-03-01"
    assert listed["content"] == "계약 논의\n다음 주"
    assert listed["author"]["label"] == "사용자 kim"
    assert listed["author"]["resigned"] is False
    assert not listed["created_at"].endswith("Z")


@pytest.mark.parametrize(
    ("sort", "order", "expected"),
    [
        ("meeting_date", "asc", ["Cherry", "apple", "banana"]),
        ("meeting_date", "desc", ["banana", "apple", "Cherry"]),
        ("partner", "asc", ["Cherry", "banana", "apple"]),
        ("partner", "desc", ["banana", "apple", "Cherry"]),
        ("content", "asc", ["apple", "banana", "Cherry"]),
        ("content", "desc", ["Cherry", "banana", "apple"]),
        ("author", "asc", ["banana", "apple", "Cherry"]),
        ("author", "desc", ["Cherry", "banana", "apple"]),
    ],
)
async def test_each_column_sorts_both_ways(
    api: Api, sort: str, order: str, expected: list[str]
) -> None:
    """Scenario: 열 4개로 오름·내림차순 정렬하고, 동률은 미팅 날짜 내림차순을 따른다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api, company="에이컴퍼니", contact="가나다")
    await given_partner(api, company="비컴퍼니", contact="라마바")
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    await given_meeting_by(
        api, kim, company="에이컴퍼니", content="banana", meeting_date="2027-03-03"
    )
    await given_meeting_by(
        api, park, company="비컴퍼니", content="Cherry", meeting_date="2027-03-01"
    )
    await given_meeting_by(
        api, kim, company="에이컴퍼니", content="apple", meeting_date="2027-03-02"
    )
    # When
    response = await when_list_meetings(api, sort=sort, order=order)
    # Then
    then_contents_are(response, expected)


async def test_changing_the_sort_restarts_from_the_first_page_of_that_order(api: Api) -> None:
    """Scenario: 정렬을 바꿔 offset=0부터 받으면 그 정렬의 처음 10건이다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_many_meetings(api, 12)
    # When
    response = await when_list_meetings(api, sort="meeting_date", order="asc")
    # Then
    then_contents_are(response, NAMES[:10])
    then_page_is(response, total=12, offset=0, limit=10)


async def test_the_limit_is_capped_at_200(api: Api) -> None:
    """Scenario: limit 200은 되고 201이나 0은 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    largest = await when_list_meetings(api, limit=200)
    too_big = await when_list_meetings(api, limit=201)
    zero = await when_list_meetings(api, limit=0)
    # Then
    then_status_is(largest, 200)
    then_problem_is(too_big, status=422, type_suffix="request-validation")
    then_problem_is(zero, status=422, type_suffix="request-validation")


async def test_an_empty_store_lists_nothing(api: Api) -> None:
    """Scenario: 기록이 없으면 빈 목록과 total 0이다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_list_meetings(api)
    # Then
    then_contents_are(response, [])
    then_page_is(response, total=0, offset=0, limit=10)


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_every_logged_in_role_can_read_the_list(api: Api, role: str) -> None:
    """Scenario: 어느 역할이든 로그인하면 목록을 본다."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    await given_many_meetings(api, 2)
    await given_logged_in_as(api, role=role)  # type: ignore[arg-type]
    # When
    response = await when_list_meetings(api)
    # Then
    then_status_is(response, 200)
    then_page_is(response, total=2, offset=0, limit=10)


async def test_anonymous_requests_are_401(api: Api) -> None:
    """Scenario: 로그인하지 않고 목록을 부르면 401(unauthenticated)이다."""
    # Given
    await given_logged_in_as(api)
    await given_logged_out(api)
    # When
    response = await when_list_meetings(api)
    # Then
    then_problem_is(response, status=401, type_suffix="unauthenticated")


@pytest.mark.parametrize("params", [{"deal": "erp"}, {"sort": "deal"}])
async def test_the_deal_parameter_and_sort_are_rejected(api: Api, params: dict[str, str]) -> None:
    """Scenario: 목록에 deal 조건이나 sort=deal을 주면 request-validation 오류다."""
    # Given
    await given_logged_in_as(api)
    # When
    response = await when_list_meetings(api, **params)
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")


async def test_deal_options_endpoint_no_longer_exists(api: Api) -> None:
    """Scenario: 폐지된 Deal 선택지 경로는 성공하지 않는다(PUT·DELETE만 있는 경로라 405)."""
    # Given
    await given_logged_in_as(api)
    await given_partner(api)
    # When
    response = await when_get_deal_options(api, HANBIT)
    # Then
    assert response.status_code == 405, response.text
