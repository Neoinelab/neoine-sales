"""서버 시각 feature의 step.

Given은 서버 시계(`api.clock`)를 UTC 순간으로 맞추고(로그인보다 먼저) 공개 API로 사용자·Deal을
만든다. When은 HTTP API 하나를 호출한다. Then은 응답 문자열의 오프셋과 순간만 본다.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from tests.functional.steps.deals import given_clock_at

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

TIME: Final = "/api/v1/time"
SEOUL_OFFSET: Final = "+09:00"


# --- Given ---


async def given_server_clock_at_utc(api: Api, *moment: int) -> None:
    """서버 시계를 UTC 순간으로 맞춘다(year, month, day, hour, minute). 로그인보다 먼저 부른다."""
    await given_clock_at(api, datetime(*moment, tzinfo=UTC))  # type: ignore[arg-type, misc]


# --- When (HTTP API 하나) ---


async def when_get_server_time(api: Api) -> Response:
    return await api.get(TIME)


# --- Then ---


def then_instant_is_server_clock(stamp: str, api: Api) -> None:
    """문자열의 순간이 서버 시계와 같다(표기 형식과 무관)."""
    assert datetime.fromisoformat(stamp) == api.clock.now(), stamp


def then_carries_seoul_offset(stamp: str) -> None:
    assert stamp.endswith(SEOUL_OFFSET), stamp
