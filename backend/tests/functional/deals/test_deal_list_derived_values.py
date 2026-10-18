"""Feature: 목록에서 다음 진행 계획·마지막 갱신·필터용 목록·삭제 영향을 본다.

next_action은 가장 최근에 수행한 Action의 다음 진행 계획, last_updated_at은 Deal 수정과 그 Action
수행 시각 중 늦은 쪽(기본 정렬 기준)이다. facets는 빈 값을 뺀 Vendor·Solution이고, 삭제 영향은
지우면 함께 사라지는 이력·활동 건수다(첨부는 항상 0).
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.auth import given_logged_in_as, given_logged_out
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_lists import (
    IMPACT_KEYS,
    given_action,
    then_codes_are,
    then_facets_are,
    then_impact_is,
    when_get_deletion_impact,
    when_get_facets,
)
from tests.functional.steps.deal_risk import given_due_in
from tests.functional.steps.deals import (
    NOT_FOUND,
    given_deal,
    when_get_deal,
    when_list_deals,
    when_update_deal,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_the_list_shows_the_next_action_and_the_action_time_as_last_update(api: Api) -> None:
    """Scenario: 최근 Action의 다음 진행 계획이 목록에 보이고 last_updated_at이 그 시각이다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    acted_at = api.clock.now() + timedelta(days=3)
    due_date = given_due_in(api, 30)  # 시계 기준 날짜: 실제 날짜가 흘러도 기한초과가 되지 않는다
    await given_action(
        api,
        deal["code"],
        login_id=login,
        acted_at=acted_at,
        next_action="계약서 검토",
        due_date=due_date,
    )
    # When
    response = await when_list_deals(api)
    # Then
    (row,) = response.json()["items"]
    assert row["next_action"] == {"text": "계약서 검토", "due_date": due_date}
    assert datetime.fromisoformat(row["last_updated_at"]) == acted_at
    assert row["risk"] is None


async def test_the_latest_acted_action_wins_and_the_detail_shows_the_same(api: Api) -> None:
    """Scenario: 수행 시각이 가장 늦은 Action이 다음 진행 계획이 되고 상세에도 같은 값이 보인다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    base = api.clock.now()
    await given_action(
        api, deal["code"], login_id=login, acted_at=base + timedelta(days=5), next_action="나중 일"
    )
    await given_action(
        api,
        deal["code"],
        login_id=login,
        acted_at=base + timedelta(days=2),
        next_action="먼저 한 일",
    )
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    then_status_is(response, 200)
    assert response.json()["next_action"]["text"] == "나중 일"


async def test_a_recent_action_moves_an_older_deal_to_the_top_of_the_default_list(
    api: Api,
) -> None:
    """Scenario: 최근 Action이 있는 Deal은 나중에 만든 Deal보다 위에 온다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    older = await given_deal(api, name="오래된 딜")
    newer = await given_deal(api, name="새 딜")
    await given_action(
        api, older["code"], login_id=login, acted_at=api.clock.now() + timedelta(days=1)
    )
    # When
    response = await when_list_deals(api)
    # Then
    then_codes_are(response, [older["code"], newer["code"]])


async def test_a_deal_without_actions_shows_no_next_action(api: Api) -> None:
    """Scenario: Action이 없으면 next_action은 null이고 last_updated_at은 수정 시각이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    api.clock.advance(60)
    await when_update_deal(api, deal["code"], name="수정")
    # When
    response = await when_get_deal(api, deal["code"])
    # Then
    body = response.json()
    assert body["next_action"] is None
    assert body["last_updated_at"] == body["updated_at"]


async def test_facets_list_the_distinct_non_blank_values_sorted_ignoring_case(api: Api) -> None:
    """Scenario: 필터용 목록은 빈 값을 뺀 Vendor·Solution을 대소문자 무시로 정렬해 준다."""
    # Given
    await given_logged_in_as(api, role="sales")
    await given_deal(api, vendor="sap", solution="Zeta")
    await given_deal(api, vendor="Oracle", solution="alpha")
    await given_deal(api, vendor="sap", solution="Beta")
    await given_deal(api, vendor="", solution="")
    # When
    response = await when_get_facets(api)
    # Then
    then_status_is(response, 200)
    then_facets_are(response, vendors=["Oracle", "sap"], solutions=["alpha", "Beta", "Zeta"])


async def test_facets_of_an_empty_system_are_empty_lists(api: Api) -> None:
    """Scenario: Deal이 없으면 두 목록이 비어 있다(facets 경로가 code 경로에 가려지지 않는다)."""
    # Given
    await given_logged_in_as(api, role="user")
    # When
    response = await when_get_facets(api)
    # Then
    then_status_is(response, 200)
    then_facets_are(response, vendors=[], solutions=[])


async def test_the_deletion_impact_counts_history_and_actions(api: Api) -> None:
    """Scenario: 삭제 영향은 History(등록·수정·Action 포함)·Action 건수를 알리고 첨부는 0이다."""
    # Given
    login = await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await when_update_deal(api, deal["code"], name="변경")
    when = api.clock.now() + timedelta(days=1)
    await given_action(api, deal["code"], login_id=login, acted_at=when)
    await given_action(api, deal["code"], login_id=login, acted_at=when + timedelta(days=1))
    # When
    response = await when_get_deletion_impact(api, deal["code"])
    # Then
    then_status_is(response, 200)
    assert set(response.json()) == IMPACT_KEYS
    # History = 등록 1 + 수정 1 + Action 2 (등록·Action도 History 행이다)
    then_impact_is(response, history=4, actions=2)


async def test_any_logged_in_role_may_read_the_deletion_impact(api: Api) -> None:
    """Scenario: 조회 전용(user) 역할도 삭제 영향을 볼 수 있다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_in_as(api, role="user")
    # When
    response = await when_get_deletion_impact(api, deal["code"])
    # Then
    then_status_is(response, 200)
    then_impact_is(response, history=1, actions=0)


@pytest.mark.parametrize("code", ["20260101-ZZZZ", "not-a-code"])
async def test_the_deletion_impact_of_an_unknown_or_malformed_code_is_not_found(
    api: Api, code: str
) -> None:
    """Scenario: 없는 Deal이나 형식이 틀린 code의 삭제 영향은 404이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    # When
    response = await when_get_deletion_impact(api, code)
    # Then
    then_problem_is(response, status=404, type_suffix="not-found")
    assert response.json()["detail"] == NOT_FOUND


async def test_facets_and_the_deletion_impact_need_a_login(api: Api) -> None:
    """Scenario: 로그인하지 않으면 facets와 삭제 영향은 401이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_logged_out(api)
    # When
    facets = await when_get_facets(api)
    impact = await when_get_deletion_impact(api, deal["code"])
    # Then
    then_problem_is(facets, status=401, type_suffix="unauthenticated")
    then_problem_is(impact, status=401, type_suffix="unauthenticated")
