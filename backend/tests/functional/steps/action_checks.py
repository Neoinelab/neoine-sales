"""Action feature의 Then step: 응답과 다시 조회한 결과로 관찰 가능한 결과를 확인한다."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from tests.functional.steps.actions import ACTION_KEYS, when_get_action, when_list_actions
from tests.functional.steps.common import then_status_is
from tests.support.functional_clock import active_clock

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api


def names_of(response: Response) -> list[str]:
    """목록 응답 항목의 진행사항(action)."""
    return [str(item["action"]) for item in response.json()["items"]]


def then_action_names_are(response: Response, expected: list[str]) -> None:
    then_status_is(response, 200)
    assert names_of(response) == expected, response.json()


def then_action_type_is(response: Response, name: str) -> None:
    """응답의 action_type이 `{id, name}`이고 이름이 name이다."""
    action_type = response.json()["action_type"]
    assert set(action_type) == {"id", "name"}, action_type
    assert action_type["name"] == name, action_type


def then_action_has_the_documented_keys(response: Response) -> None:
    assert set(response.json()) == ACTION_KEYS, response.json()


def then_acted_at_is_the_server_time(response: Response) -> None:
    """수행 일시가 요청 시점의 서버 시계 값이다(본문으로 정할 수 없다)."""
    assert datetime.fromisoformat(response.json()["acted_at"]) == active_clock().now()


def same_instant(left: object, right: object) -> bool:
    """두 ISO 시각 문자열이 같은 순간이다(엔드포인트마다 시간대 표기가 다를 수 있다)."""
    return datetime.fromisoformat(str(left)) == datetime.fromisoformat(str(right))


def then_detail_is(response: Response, detail: str) -> None:
    assert response.json()["detail"] == detail, response.json()


def then_body_has(response: Response, **fields: object) -> None:
    body = response.json()
    assert {key: body.get(key) for key in fields} == fields, body


def normalized(body: dict[str, Any]) -> dict[str, Any]:
    """시각 필드를 순간(datetime)으로 바꿔 시간대 표기 차이를 무시하고 비교할 수 있게 한다."""
    times = ("acted_at", "created_at", "updated_at")
    return {
        key: datetime.fromisoformat(value) if key in times else value for key, value in body.items()
    }


async def then_action_is_unchanged(api: Api, before: dict[str, Any]) -> None:
    """다시 조회한 Action이 기억해 둔 응답과 같다(시각은 같은 순간이면 같다)."""
    response = await when_get_action(api, str(before["id"]))
    then_status_is(response, 200)
    assert normalized(response.json()) == normalized(before)


async def then_action_is_gone(api: Api, action_id: str) -> None:
    then_status_is(await when_get_action(api, action_id), 404)


async def then_deal_has_no_actions(api: Api, code: str) -> None:
    response = await when_list_actions(api, code)
    then_status_is(response, 200)
    assert response.json() == {"items": []}
