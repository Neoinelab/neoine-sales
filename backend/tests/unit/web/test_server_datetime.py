"""ServerDateTime: 응답의 시각을 서버 OS 로컬 오프셋으로 직렬화한다.

순간은 바뀌지 않고, openapi의 필드 스키마(string/date-time, nullable 여부)도 바뀌지 않는다.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.web.schemas.server_datetime import ServerDateTime

if TYPE_CHECKING:
    from collections.abc import Callable

MOMENT = datetime(2026, 10, 22, 15, 30, tzinfo=UTC)


class _Body(BaseModel):
    at: ServerDateTime
    maybe: ServerDateTime | None = None


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/probe", response_model=_Body)
    async def probe() -> _Body:
        return _Body(at=MOMENT, maybe=MOMENT)

    return app


def test_serializes_with_server_offset(local_tz: Callable[[str], None]) -> None:
    """응답 시각은 서버 오프셋 문자열로 나간다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 모델을 JSON(mode=json)으로 만든다
    body = _Body(at=MOMENT).model_dump(mode="json")

    # then: +09:00 문자열
    assert body["at"] == "2026-10-23T00:30:00+09:00"


def test_json_string_output_also_carries_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    """JSON 문자열 출력(model_dump_json)도 서버 오프셋이다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: model_dump_json
    text = _Body(at=MOMENT).model_dump_json()

    # then: +09:00 문자열
    assert '"at":"2026-10-23T00:30:00+09:00"' in text


def test_instant_is_unchanged_after_a_round_trip(local_tz: Callable[[str], None]) -> None:
    """다시 읽으면 원래와 같은 순간이다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 직렬화한 문자열을 다시 읽는다
    text = _Body(at=MOMENT).model_dump(mode="json")["at"]

    # then: 순간이 같다
    assert datetime.fromisoformat(text) == MOMENT


def test_other_offset_input_is_serialized_with_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    """다른 오프셋 입력도 서버 오프셋으로 직렬화한다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul, -04:00 오프셋 입력
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 20, 0, tzinfo=timezone(timedelta(hours=-4)))

    # when: 순간을 직렬화한다
    actual = _Body(at=moment).model_dump(mode="json")["at"]
    # then: +09:00 표기다
    assert actual == "2026-10-23T09:00:00+09:00"


def test_offset_follows_the_process_timezone(local_tz: Callable[[str], None]) -> None:
    """응답 시각 오프셋은 서버 프로세스 시간대를 따른다.

    테스트 코드: TM-018
    """
    # given: 서버 시간대 America/New_York
    local_tz("America/New_York")
    # when: -04:00 시간대의 순간을 직렬화한다
    actual = _Body(at=MOMENT).model_dump(mode="json")["at"]
    # then: -04:00 표기다
    assert actual == "2026-10-22T11:30:00-04:00"


def test_microseconds_are_kept(local_tz: Callable[[str], None]) -> None:
    """마이크로초가 유지된다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul, 마이크로초가 있는 시각
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 15, 30, 1, 123456, tzinfo=UTC)

    # when: 마이크로초가 있는 순간을 직렬화한다
    actual = _Body(at=moment).model_dump(mode="json")["at"]
    # then: 마이크로초가 유지된 문자열이다
    assert actual == "2026-10-23T00:30:01.123456+09:00"


def test_none_stays_null() -> None:
    """비어 있는 시각은 null이다.

    테스트 코드: TM-019
    """
    # when: 선택 필드를 비워 직렬화한다
    body = _Body(at=MOMENT, maybe=None).model_dump(mode="json")

    # then: null
    assert body["maybe"] is None


async def test_fastapi_response_carries_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    """FastAPI 응답도 서버 오프셋이다.

    테스트 코드: TM-017
    """
    # given: 서버 시간대 Asia/Seoul
    local_tz("Asia/Seoul")
    # when: 응답 모델을 쓰는 라우트를 호출한다
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as http:
        response = await http.get("/probe")

    # then: +09:00 문자열
    assert response.json() == {
        "at": "2026-10-23T00:30:00+09:00",
        "maybe": "2026-10-23T00:30:00+09:00",
    }


def _strip_titles(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k != "title"}


def test_openapi_schema_is_unchanged() -> None:
    """openapi 필드 스키마는 일반 date-time과 같다.

    테스트 코드: TM-019
    """
    # when: openapi 문서를 만든다
    openapi = _app().openapi()
    properties = openapi["components"]["schemas"]["_Body"]["properties"]

    # then: string/date-time, nullable은 anyOf [date-time, null]
    assert _strip_titles(properties["at"]) == {"type": "string", "format": "date-time"}
    assert _strip_titles(properties["maybe"]) == {
        "anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]
    }


def test_required_and_optional_fields_keep_their_requiredness() -> None:
    """필수·선택 여부가 유지된다.

    테스트 코드: TM-019
    """
    # when: openapi 문서를 만든다
    schema = _app().openapi()["components"]["schemas"]["_Body"]

    # then: at만 required
    assert "at" in schema["required"]
    assert "maybe" not in schema.get("required", [])
