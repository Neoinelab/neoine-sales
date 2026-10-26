"""Feature: Action을 저장하면서 이전 Next Action을 같은 트랜잭션에서 종료(수행)로 바꿀 수 있다.

요청의 `close_previous_next_action_id`는 그 Deal의 지금 기준 행(Next Action이 있는 가장 최근
Action)의 id여야 한다. 아니면 409이고 아무것도 저장되지 않는다. 이미 종료된 기준 행은 건너뛰고,
sales는 본인 Action만(admin은 모두) 닫을 수 있다. 저장이 실패하면 이전 행도 바뀌지 않는다.
판정 순서: 404(Deal) -> 422(입력) -> 409(기준 행 변경) -> 403(권한) -> Status 동기화 판정.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.action_checks import same_instant
from tests.functional.steps.action_close_previous import (
    CHANGED,
    CLOSED_ROW,
    CREATED_ROW,
    STATUS_FORBIDDEN,
    actions_of,
    closing_body,
    then_action_count_is,
    then_history_tail_is,
    then_previous_is_done_at,
    then_previous_is_open,
    when_register_closing,
    when_register_closing_as,
    when_register_with_body,
)
from tests.functional.steps.actions import (
    given_action,
    given_action_by,
    given_deal_with_a_sales_owner,
    when_register_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_problem_is, then_status_is
from tests.functional.steps.deal_changes import REVENUE_REQUIRED
from tests.functional.steps.deals import (
    given_deal,
    history_rows,
    when_get_deal,
    when_list_history,
)
from tests.functional.steps.next_action_status import given_status_changed
from tests.functional.steps.users import given_signed_in_session
from tests.support.ids import MISSING_ID

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_saving_an_action_closes_the_previous_next_action_as_done(api: Api) -> None:
    """Scenario: 이전 Next Action id와 함께 저장하면 새 Action이 생기고 이전 행이 종료(수행)된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_closing(
        api, deal["code"], previous["id"], next_action="다음 일정 확인", due_date="2027-02-01"
    )
    # Then
    then_status_is(response, 201)
    await then_previous_is_done_at(api, deal["code"], previous["id"], response.json())
    await then_action_count_is(api, deal["code"], 2)
    detail = (await when_get_deal(api, deal["code"])).json()
    assert detail["next_action"]["text"] == "다음 일정 확인"  # 목록·상세의 기준 행은 새 Action


async def test_saving_writes_the_status_line_then_the_registration_line(api: Api) -> None:
    """Scenario: History에 종료(수행) 줄이 남고 이어서 등록 줄이 남는다(목록에서는 등록 줄이 위)."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_closing(api, deal["code"], previous["id"])
    # Then
    then_status_is(response, 201)
    await then_history_tail_is(api, deal["code"], [CLOSED_ROW, CREATED_ROW])
    newest_first = (await when_list_history(api, deal["code"])).json()
    assert [e["target"] for e in newest_first[:2]] == ["Action", "Next Action"]
    assert same_instant(newest_first[0]["at"], newest_first[1]["at"])


async def test_saving_without_the_field_leaves_the_previous_next_action_open(api: Api) -> None:
    """Scenario: 필드를 빼면 지금과 똑같이 이전 Next Action은 Open으로 남는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_action(api, deal["code"])
    # Then
    then_status_is(response, 201)
    await then_previous_is_open(api, deal["code"], previous["id"])


async def test_saving_with_a_null_field_leaves_the_previous_next_action_open(api: Api) -> None:
    """Scenario: null을 보내도 필드를 뺀 것과 같다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_closing(api, deal["code"], None)
    # Then
    then_status_is(response, 201)
    await then_previous_is_open(api, deal["code"], previous["id"])


async def test_stale_previous_id_is_409_and_nothing_is_saved(api: Api) -> None:
    """Scenario: 그 사이 더 최근 Next Action이 생겼으면 409이고 새 Action도 저장되지 않는다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    stale = await given_action_by(api, kim, deal["code"])
    await given_action_by(api, kim, deal["code"], action="그 사이 추가")
    rows_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_register_closing_as(api, kim, deal["code"], stale["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    assert response.json()["detail"] == CHANGED
    await then_action_count_is(api, deal["code"], 2)
    await then_previous_is_open(api, deal["code"], stale["id"])
    assert history_rows(await when_list_history(api, deal["code"])) == rows_before


async def test_an_action_id_of_another_deal_is_409(api: Api) -> None:
    """Scenario: 다른 Deal의 Action id는 409이고 아무것도 저장되지 않는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    other = await given_deal(api, name="다른 Deal")
    mine = await given_action(api, deal["code"])
    foreign = await given_action(api, other["code"])
    # When
    response = await when_register_closing(api, deal["code"], foreign["id"])
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    await then_action_count_is(api, deal["code"], 1)
    await then_previous_is_open(api, deal["code"], mine["id"])
    await then_previous_is_open(api, other["code"], foreign["id"])


async def test_an_unknown_action_id_is_409(api: Api) -> None:
    """Scenario: 없는 Action id도 기준 행이 아니므로 409이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    await given_action(api, deal["code"])
    # When
    response = await when_register_closing(api, deal["code"], MISSING_ID)
    # Then
    then_problem_is(response, status=409, type_suffix="invalid-state")
    await then_action_count_is(api, deal["code"], 1)


async def test_already_closed_previous_is_left_as_is(api: Api) -> None:
    """Scenario: 이미 종료된 기준 행은 상태·종료 시각을 바꾸지 않고 새 Action만 저장한다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    closed = await given_status_changed(api, previous["id"], "not_done", "못 함")
    rows_before = history_rows(await when_list_history(api, deal["code"]))
    # When
    response = await when_register_closing(api, deal["code"], previous["id"])
    # Then
    then_status_is(response, 201)
    found = next(a for a in await actions_of(api, deal["code"]) if a["id"] == previous["id"])
    assert found["next_action_status"] == "not_done"
    assert same_instant(found["next_action_closed_at"], closed["next_action_closed_at"])
    assert history_rows(await when_list_history(api, deal["code"])) == [*rows_before, CREATED_ROW]


async def test_sales_cannot_close_another_users_next_action(api: Api) -> None:
    """Scenario: 다른 sales의 기준 행이면 403이고 새 Action도 저장되지 않는다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    park = await given_signed_in_session(api, login_id="park", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    previous = await given_action_by(api, kim, deal["code"])
    # When
    response = await when_register_closing_as(api, park, deal["code"], previous["id"])
    # Then
    then_problem_is(response, status=403, type_suffix="forbidden")
    assert response.json()["detail"] == STATUS_FORBIDDEN
    await then_action_count_is(api, deal["code"], 1)
    await then_previous_is_open(api, deal["code"], previous["id"])


async def test_admin_closes_anyones_next_action(api: Api) -> None:
    """Scenario: admin은 다른 사람의 기준 행도 닫을 수 있다."""
    # Given
    kim = await given_signed_in_session(api, login_id="kim", role="sales")
    deal = await given_deal_with_a_sales_owner(api)
    previous = await given_action_by(api, kim, deal["code"])
    # When
    response = await when_register_closing(api, deal["code"], previous["id"])
    # Then
    then_status_is(response, 201)
    await then_previous_is_done_at(api, deal["code"], previous["id"], response.json())


async def test_invalid_content_is_422_and_the_previous_stays_open(api: Api) -> None:
    """Scenario: 진행사항·Next Action이 모두 비면 422이고 이전 행은 Open 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_closing(
        api, deal["code"], previous["id"], action="", next_action=""
    )
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    await then_previous_is_open(api, deal["code"], previous["id"])
    await then_action_count_is(api, deal["code"], 1)


async def test_a_failing_status_change_keeps_the_previous_open(api: Api) -> None:
    """Scenario: 함께 보낸 Status 변경이 거절되면 이전 행은 Open 그대로이고 새 Action도 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)  # 계약완료로의 변경은 확정 매출 정보 없이는 거절된다
    previous = await given_action(api, deal["code"])
    body = {
        **closing_body(previous["id"]),
        "status_change": {"change": {"field": "status_key", "value": "contract_completed"}},
    }
    # When
    response = await when_register_with_body(api, deal["code"], body)
    # Then
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == REVENUE_REQUIRED
    await then_action_count_is(api, deal["code"], 1)
    await then_previous_is_open(api, deal["code"], previous["id"])


@pytest.mark.parametrize("bad", ["7", 0, -1, 1.5, True, [1]])
async def test_malformed_previous_id_is_422(api: Api, bad: object) -> None:
    """Scenario: 양의 정수가 아닌 값은 422 request-validation이다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    previous = await given_action(api, deal["code"])
    # When
    response = await when_register_with_body(api, deal["code"], closing_body(bad))
    # Then
    then_problem_is(response, status=422, type_suffix="request-validation")
    await then_previous_is_open(api, deal["code"], previous["id"])
