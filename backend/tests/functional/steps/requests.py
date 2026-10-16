"""영역에 묶이지 않는 When step(단일 HTTP 호출)과 여러 응답을 묶어 보는 Then step."""

from typing import TYPE_CHECKING

from tests.functional.steps.common import then_response_does_not_mention, then_status_is

if TYPE_CHECKING:
    from collections.abc import Iterable

    from httpx import Response

    from tests.functional.conftest import Api, Params

CSRF_HEADER_NAME = "X-Requested-With"


async def when_get(api: Api, url: str, *, params: Params | None = None) -> Response:
    """현재 로그인 상태(쿠키)로 GET 한다."""
    return await api.get(url, params=params)


async def when_request(
    api: Api,
    method: str,
    url: str,
    *,
    json: object = None,
    headers: dict[str, str] | None = None,
) -> Response:
    """현재 로그인 상태(쿠키)로 임의의 메서드를 요청한다."""
    return await api.request(method, url, json=json, headers=headers)


async def when_request_without_csrf_header(
    api: Api, method: str, url: str, *, json: object = None
) -> Response:
    """CSRF 헤더 없이 요청한다(빈 값은 없는 것과 같게 거부된다)."""
    return await api.request(method, url, json=json, headers={CSRF_HEADER_NAME: ""})


def then_no_response_mentions(responses: Iterable[Response], *fragments: str) -> None:
    """모든 응답(본문·헤더 값)에 내부 정보 조각이 드러나지 않는다."""
    for response in responses:
        then_response_does_not_mention(response, *fragments)


async def then_get_is(api: Api, url: str, status: int) -> None:
    """현재 로그인 상태로 url을 다시 조회하면 주어진 상태 코드다."""
    then_status_is(await api.get(url), status)
