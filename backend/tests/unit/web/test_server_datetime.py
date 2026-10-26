"""ServerDateTime: 응답의 시각을 서버 OS 로컬 오프셋으로 직렬화한다(시간 기준 서버 통일 AC2).

순간은 바뀌지 않고, openapi의 필드 스키마(string/date-time, nullable 여부)도 바뀌지 않는다.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.web.schemas.server_datetime import ServerDateTime
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

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
    local_tz("Asia/Seoul")

    body = _Body(at=MOMENT).model_dump(mode="json")

    assert body["at"] == "2026-10-23T00:30:00+09:00"


def test_json_string_output_also_carries_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")

    text = _Body(at=MOMENT).model_dump_json()

    assert '"at":"2026-10-23T00:30:00+09:00"' in text


def test_instant_is_unchanged_after_a_round_trip(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")

    text = _Body(at=MOMENT).model_dump(mode="json")["at"]

    assert datetime.fromisoformat(text) == MOMENT


def test_other_offset_input_is_serialized_with_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 20, 0, tzinfo=timezone(timedelta(hours=-4)))

    assert _Body(at=moment).model_dump(mode="json")["at"] == "2026-10-23T09:00:00+09:00"


def test_offset_follows_the_process_timezone(local_tz: Callable[[str], None]) -> None:
    local_tz("America/New_York")

    assert _Body(at=MOMENT).model_dump(mode="json")["at"] == "2026-10-22T11:30:00-04:00"


def test_microseconds_are_kept(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")
    moment = datetime(2026, 10, 22, 15, 30, 1, 123456, tzinfo=UTC)

    assert _Body(at=moment).model_dump(mode="json")["at"] == "2026-10-23T00:30:01.123456+09:00"


def test_none_stays_null() -> None:
    body = _Body(at=MOMENT, maybe=None).model_dump(mode="json")

    assert body["maybe"] is None


async def test_fastapi_response_carries_the_server_offset(
    local_tz: Callable[[str], None],
) -> None:
    local_tz("Asia/Seoul")
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://test") as http:
        response = await http.get("/probe")

    assert response.json() == {
        "at": "2026-10-23T00:30:00+09:00",
        "maybe": "2026-10-23T00:30:00+09:00",
    }


def _strip_titles(schema: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in schema.items() if k != "title"}


def test_openapi_schema_is_unchanged() -> None:
    openapi = _app().openapi()
    properties = openapi["components"]["schemas"]["_Body"]["properties"]

    assert _strip_titles(properties["at"]) == {"type": "string", "format": "date-time"}
    assert _strip_titles(properties["maybe"]) == {
        "anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]
    }


def test_required_and_optional_fields_keep_their_requiredness() -> None:
    schema = _app().openapi()["components"]["schemas"]["_Body"]

    assert "at" in schema["required"]
    assert "maybe" not in schema.get("required", [])
