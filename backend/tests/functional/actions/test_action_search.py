"""Feature: 영업은 Deal 상세에서 그 Deal의 Action을 조건으로 찾고 정렬한다.

조건(유형·담당자·검색어·수행일·Due Date)은 AND로 결합하고, 수행일은 OS 로컬 업무 날짜 기준 양끝
포함이다. 정렬은 수행일시 최신순(기본)·오래된 순·Due Date 순 세 가지이고, 페이지 없이 전부 돌려준다.
전역 검색(GET /deal-actions)은 폐지됐다.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from tests.functional.steps.action_types import given_type_id, when_rename_type
from tests.functional.steps.actions import (
    given_action,
    given_action_at_as,
    given_searchable_actions,
    then_action_names_are,
    when_list_actions,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.deals import given_deal

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration

NEWEST_FIRST = ["킥오프 2", "견적 발송", "킥오프"]
MIDNIGHT = datetime(2027, 5, 20).astimezone()  # 서버와 같은 OS 로컬 시간대의 자정
ONE_MINUTE = timedelta(minutes=1)


async def test_filters_combine_within_a_deal(api: Api) -> None:
    """Scenario: 유형과 담당자 조건은 AND로 결합된다."""
    # Given
    code, park_id = await given_searchable_actions(api)
    # When
    meeting = await given_type_id(api, "미팅")
    response = await when_list_actions(api, code, action_type_id=meeting, actor_user_id=park_id)
    # Then
    then_action_names_are(response, ["킥오프 2"])


async def test_type_filter_matches_the_type_id_even_after_a_rename(api: Api) -> None:
    """Scenario: 유형 id로 거르고, 유형 이름을 바꿔도 같은 id로 같은 Action이 나온다(AC-16)."""
    # Given
    code, _ = await given_searchable_actions(api)
    email = await given_type_id(api, "이메일")
    await when_rename_type(api, email, "메일")
    # When
    response = await when_list_actions(api, code, action_type_id=email)
    # Then
    then_action_names_are(response, ["견적 발송"])
    assert response.json()["items"][0]["action_type"] == {"id": email, "name": "메일"}


async def test_an_unknown_type_id_lists_nothing(api: Api) -> None:
    """Scenario: 없는 유형 id로 찾으면 오류 없이 0건이다(AC-16)."""
    # Given
    code, _ = await given_searchable_actions(api)
    # When
    response = await when_list_actions(api, code, action_type_id=str(uuid4()))
    # Then
    then_action_names_are(response, [])


async def test_without_conditions_every_action_is_listed_newest_first(api: Api) -> None:
    """Scenario: 조건이 없으면 Deal의 Action 전부가 수행일시 최신순으로 나온다."""
    # Given
    code, _ = await given_searchable_actions(api)
    # When
    response = await when_list_actions(api, code)
    # Then
    then_action_names_are(response, NEWEST_FIRST)
    assert set(response.json()) == {"items"}


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        pytest.param("킥오프", ["킥오프 2", "킥오프"], id="progress"),
        pytest.param("계약서", ["킥오프 2"], id="next-action"),
        pytest.param("협의", ["킥오프"], id="memo"),
        pytest.param("100%", ["견적 발송"], id="percent-is-literal"),
        pytest.param("_", [], id="underscore-is-literal"),
        pytest.param("  견적  ", ["견적 발송"], id="trimmed"),
    ],
)
async def test_keyword_matches_progress_next_action_and_memo(
    api: Api, keyword: str, expected: list[str]
) -> None:
    """Scenario: 검색어는 진행사항·Next Action·Memo에서 부분 일치하고 와일드카드는 글자 그대로다."""
    # Given
    code, _ = await given_searchable_actions(api)
    # When
    response = await when_list_actions(api, code, keyword=keyword)
    # Then
    then_action_names_are(response, expected)


async def test_keyword_ignores_case(api: Api) -> None:
    """Scenario: 검색어는 대소문자를 구분하지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(api, deal["code"], action="Kickoff Meeting")
    # When
    response = await when_list_actions(api, deal["code"], keyword="KICKOFF")
    # Then
    then_action_names_are(response, ["Kickoff Meeting"])


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param(
            {"due_from": "2027-04-01", "due_to": "2027-04-10"}, NEWEST_FIRST, id="both-ends"
        ),
        pytest.param({"due_from": "2027-04-10"}, ["킥오프 2", "킥오프"], id="from-inclusive"),
        pytest.param({"due_to": "2027-04-01"}, ["견적 발송"], id="to-inclusive"),
        pytest.param({"due_from": "2027-04-02", "due_to": "2027-04-09"}, [], id="empty-window"),
        pytest.param(
            {"due_from": "2027-04-01", "due_to": "2027-04-01"}, ["견적 발송"], id="one-day"
        ),
    ],
)
async def test_due_range_is_inclusive_on_both_ends(
    api: Api, params: dict[str, str], expected: list[str]
) -> None:
    """Scenario: Due Date 범위는 양끝을 포함한다."""
    # Given
    code, _ = await given_searchable_actions(api)
    # When
    response = await when_list_actions(api, code, **params)
    # Then
    then_action_names_are(response, expected)


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        pytest.param("acted_at_desc", ["킥오프 2", "견적 발송", "킥오프"], id="newest-first"),
        pytest.param("acted_at_asc", ["킥오프", "견적 발송", "킥오프 2"], id="oldest-first"),
        pytest.param("due_date_asc", ["견적 발송", "킥오프 2", "킥오프"], id="due-date"),
    ],
)
async def test_sorting_orders_the_actions(api: Api, sort: str, expected: list[str]) -> None:
    """Scenario: 정렬은 수행일시 최신순·오래된 순·Due Date 순이고 동률은 최신 수행이 먼저다."""
    # Given
    code, _ = await given_searchable_actions(api)
    # When
    response = await when_list_actions(api, code, sort=sort)
    # Then
    then_action_names_are(response, expected)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        pytest.param(
            {"acted_from": "2027-05-20", "acted_to": "2027-05-20"},
            ["당일 23:59", "당일 00:00"],
            id="whole-local-day",
        ),
        pytest.param(
            {"acted_from": "2027-05-20"},
            ["다음날 00:00", "당일 23:59", "당일 00:00"],
            id="from-inclusive",
        ),
        pytest.param(
            {"acted_to": "2027-05-20"},
            ["당일 23:59", "당일 00:00", "전날 23:59"],
            id="to-inclusive",
        ),
    ],
)
async def test_acted_date_range_covers_whole_days(
    api: Api, params: dict[str, str], expected: list[str]
) -> None:
    """Scenario: 수행일 조건은 로컬 업무 날짜의 00:00부터 24:00까지를 양끝 포함으로 본다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    moments = {
        "전날 23:59": MIDNIGHT - ONE_MINUTE,
        "당일 00:00": MIDNIGHT,
        "당일 23:59": MIDNIGHT + timedelta(days=1) - ONE_MINUTE,
        "다음날 00:00": MIDNIGHT + timedelta(days=1),
    }
    for name, moment in moments.items():
        await given_action_at_as(api, deal["code"], moment, login_id=login, action=name)
    # When
    response = await when_list_actions(api, deal["code"], **params)
    # Then
    then_action_names_are(response, expected)


async def test_other_deals_actions_are_not_listed(api: Api) -> None:
    """Scenario: 다른 Deal의 Action은 목록에 나오지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    mine = await given_deal(api)
    other = await given_deal(api, name="다른 딜")
    await given_action(api, mine["code"], action="내 활동")
    await given_action(api, other["code"], action="남의 활동")
    # When
    response = await when_list_actions(api, mine["code"])
    # Then
    then_action_names_are(response, ["내 활동"])
