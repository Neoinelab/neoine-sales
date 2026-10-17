"""경고 기준 feature의 step(P3): 조회·저장 요청과 응답 확인.

When은 HTTP API 하나, Then은 응답과 다시 조회한 결과만 본다. 로그인·공통 확인은 `steps/auth.py`,
`steps/common.py`, 저장 시각·저장자 확인은 `steps/settings.py`를 쓴다.
"""

from typing import TYPE_CHECKING, Final

from tests.functional.steps.common import then_problem_is, then_status_is

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

ALERT_SETTINGS: Final = "/api/v1/alert-settings"
ALERT_KEYS: Final = {"stale_days", "updated_at", "updated_by"}
DEFAULT_STALE_DAYS: Final = 14
RANGE_MESSAGE: Final = "미업데이트 기준은 1~365일 사이의 정수로 입력하세요."


async def when_read_alert_settings(api: Api) -> Response:
    return await api.get(ALERT_SETTINGS)


async def when_update_alert_settings(api: Api, stale_days: object) -> Response:
    return await api.put(ALERT_SETTINGS, json={"stale_days": stale_days})


async def when_update_alert_settings_body(api: Api, body: dict[str, object]) -> Response:
    """임의의 본문을 그대로 보낸다(누락·알 수 없는 필드 검증용)."""
    return await api.put(ALERT_SETTINGS, json=body)


async def then_stale_days_is(api: Api, expected: int) -> None:
    """다시 조회한 경고 기준이 expected일이다."""
    response = await when_read_alert_settings(api)
    then_status_is(response, 200)
    assert response.json()["stale_days"] == expected, response.json()


def then_range_is_rejected(response: Response) -> None:
    then_problem_is(response, status=422, type_suffix="invalid-value")
    assert response.json()["detail"] == RANGE_MESSAGE


def then_format_is_rejected(response: Response) -> None:
    then_problem_is(response, status=422, type_suffix="request-validation")
