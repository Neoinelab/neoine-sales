"""헬스체크(생존·준비) step."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

UNREACHABLE_DB_PASSWORD = "probe-secret-pw"  # noqa: S105 - 노출되지 않아야 하는 더미 값
UNREACHABLE_DB_URL = (
    f"postgresql+asyncpg://probe:{UNREACHABLE_DB_PASSWORD}@127.0.0.1:1/neoine_unreachable"
)


async def given_database_unreachable(api: Api) -> None:
    """앱이 접속할 수 없는 DB 주소(닫힌 포트)로 설정되어 떠 있다."""
    await api.reopen(database_url=UNREACHABLE_DB_URL)


async def when_check_liveness(api: Api) -> Response:
    return await api.get("/healthz")


async def when_check_readiness(api: Api) -> Response:
    return await api.get("/readyz")
