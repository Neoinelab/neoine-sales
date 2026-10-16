"""Feature: 영업은 Deal 상세에서 Action을 남기고, 서버가 수행 일시·담당자·상태를 기록한다.

수행 일시는 서버 시각, 담당자는 로그인한 사용자이며 둘 다 요청 본문으로 정할 수 없다. 등록 시점의
Deal Status/Forecast key가 Action에 스냅숏으로 남고, Deal History에 한 건이 쌓인다. 진행사항·
Next Action·Memo에는 길이 상한이 없다. History 요약만 1,000자에서 잘린다.
"""

from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.actions import (
    ACTION_KEYS,
    ACTIONS,
    SUMMARY,
    SUMMARY_WITH_MEMO,
    action_body,
    given_action,
    names_of,
    same_instant,
    then_acted_at_is_the_server_time,
    then_action_has_the_documented_keys,
    then_action_is_unchanged,
    then_body_has,
    when_get_action,
    when_list_actions,
    when_register_action,
)
from tests.functional.steps.auth import given_logged_in_as
from tests.functional.steps.common import then_status_is
from tests.functional.steps.deals import (
    given_deal,
    given_my_user_id,
    history_rows,
    then_deal_keeps,
    then_history_is,
    when_delete_deal,
    when_get_deal,
    when_list_history,
)

if TYPE_CHECKING:
    from tests.functional.conftest import Api

pytestmark = pytest.mark.integration


async def test_sales_records_an_action_with_current_status_and_forecast(api: Api) -> None:
    """Scenario: Action을 남기면 서버 시각·로그인 사용자·등록 시점의 Status/Forecast가 기록된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    deal = await given_deal(api, status_key="introduction", forecast_key="best")
    # When
    response = await when_register_action(api, deal["code"])
    # Then
    then_status_is(response, 201)
    body = response.json()
    assert response.headers["location"] == f"{ACTIONS}/{body['id']}"
    then_action_has_the_documented_keys(response)
    then_acted_at_is_the_server_time(response)
    then_body_has(
        response,
        deal_code=deal["code"],
        action_type="meeting",
        action="킥오프 미팅",
        next_action="요구사항 문서 전달",
        due_date="2027-01-15",
        memo="요구사항 정리",
        status_key="introduction",
        forecast_key="best",
    )
    assert (body["actor"]["id"], body["actor"]["role"]) == (me, "sales")
    assert set(body) == ACTION_KEYS
    await then_action_is_unchanged(api, body)


async def test_action_is_recorded_in_deal_history(api: Api) -> None:
    """Scenario: Action을 남기면 Deal History에 등록 한 건이 남고 요약에 Memo가 붙는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    me = await given_my_user_id(api)
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"])
    # Then
    then_status_is(response, 201)
    await then_history_is(
        api, deal["code"], [("action", "Action", "", f"등록: {SUMMARY_WITH_MEMO}")]
    )
    newest = (await when_list_history(api, deal["code"])).json()[0]
    assert newest["by"]["id"] == me
    assert datetime.fromisoformat(newest["at"]) == datetime.fromisoformat(
        response.json()["acted_at"]
    )


async def test_memo_is_left_out_of_the_history_when_empty(api: Api) -> None:
    """Scenario: Memo가 비어 있으면 History 요약에 Memo 표기가 없다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], memo="")
    # Then
    then_status_is(response, 201)
    await then_history_is(api, deal["code"], [("action", "Action", "", f"등록: {SUMMARY}")])


async def test_registering_an_action_does_not_touch_the_deal_but_updates_the_next_action(
    api: Api,
) -> None:
    """Scenario: Deal 수정 시각은 그대로이고 next_action·last_updated_at이 새 Action을 가리킨다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(
        api, deal["code"], next_action="계약서 검토", due_date="2027-02-05"
    )
    # Then
    then_status_is(response, 201)
    detail = (await when_get_deal(api, deal["code"])).json()
    assert same_instant(detail["updated_at"], deal["updated_at"])
    assert detail["next_action"] == {"text": "계약서 검토", "due_date": "2027-02-05"}
    assert same_instant(detail["last_updated_at"], response.json()["acted_at"])


async def test_long_action_text_is_saved_in_full(api: Api) -> None:
    """Scenario: 진행사항 5,000자·Next Action 5,000자·Memo 20,000자도 잘리지 않고 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(
        api, deal["code"], action="가" * 5_000, next_action="😀" * 5_000, memo="메" * 20_000
    )
    # Then
    then_status_is(response, 201)
    stored = (await when_get_action(api, response.json()["id"])).json()
    assert stored["action"] == "가" * 5_000
    assert stored["next_action"] == "😀" * 5_000
    assert stored["memo"] == "메" * 20_000


async def test_texts_are_trimmed_and_a_past_due_date_is_accepted(api: Api) -> None:
    """Scenario: 앞뒤 공백은 지워 저장하고 지난 Due Date도 받는다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(
        api,
        deal["code"],
        action="  킥오프  ",
        next_action=" 견적 ",
        memo="  메모  ",
        due_date="2000-01-01",
    )
    # Then
    then_status_is(response, 201)
    then_body_has(response, action="킥오프", next_action="견적", memo="메모", due_date="2000-01-01")


async def test_a_missing_memo_is_saved_as_empty(api: Api) -> None:
    """Scenario: Memo를 보내지 않으면 빈 문자열로 저장된다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    body = action_body()
    del body["memo"]
    # When
    response = await api.post(f"/api/v1/deals/{deal['code']}/actions", json=body)
    # Then
    then_status_is(response, 201)
    then_body_has(response, memo="")


async def test_history_summary_is_clipped_but_the_action_is_not(api: Api) -> None:
    """Scenario: 긴 진행사항은 History에서 1,000자(끝 "…")로 잘리고 Action 원문은 그대로다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    # When
    response = await when_register_action(api, deal["code"], action="가" * 2_000)
    # Then
    then_status_is(response, 201)
    (entry,) = history_rows(await when_list_history(api, deal["code"]))[1:]
    assert len(entry[3]) == 1_000
    assert entry[3].endswith("…")
    assert (await when_get_action(api, response.json()["id"])).json()["action"] == "가" * 2_000


async def test_actions_belong_to_their_deal_and_go_with_it(api: Api) -> None:
    """Scenario: Deal을 지우면 그 Deal의 Action도 함께 지워진다."""
    # Given
    await given_logged_in_as(api, role="sales")
    deal = await given_deal(api)
    other = await given_deal(api, name="다른 딜")
    mine = await given_action(api, deal["code"], action="내 활동")
    kept = await given_action(api, other["code"], action="남는 활동")
    # When
    response = await when_delete_deal(api, deal["code"])
    # Then
    then_status_is(response, 204)
    then_status_is(await when_get_action(api, mine["id"]), 404)
    then_status_is(await when_get_action(api, kept["id"]), 200)
    assert names_of(await when_list_actions(api, other["code"])) == ["남는 활동"]
    await then_deal_keeps(api, other["code"], name="다른 딜")
