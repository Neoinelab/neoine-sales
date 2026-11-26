"""준비 확인(`/readyz`)이 실제 DB 접속을 지나는 경우(PL-028·PL-029의 실제 DB 쪽).

Fake 유스케이스 위의 성공·실패는 `unit/web/test_health_routes.py`가 보고, 여기서는 실제 Container가
임시 PostgreSQL에 접속하거나 접속하지 못할 때의 응답을 본다. DB가 없으면 `skip_or_fail` 규칙을
따른다.
"""

import logging
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from app.container import Container
from app.main import create_app
from tests.support.app_settings import make_settings

if TYPE_CHECKING:
    from httpx import Response
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

PROBLEM_PREFIX = "https://neoine-sales.example/problems/"
UNREACHABLE_DB_PASSWORD = "probe-secret-pw"  # noqa: S105 - 노출되지 않아야 하는 더미 값
UNREACHABLE_DB_URL = (
    f"postgresql+asyncpg://probe:{UNREACHABLE_DB_PASSWORD}@127.0.0.1:1/neoine_unreachable"
)


async def _readyz(database_url: str, *, db_echo: bool = False) -> Response:
    settings = make_settings(database_url, db_echo=db_echo)
    container = Container(settings)
    app = create_app(settings=settings, use_cases=container)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            return await http.get("/readyz")
    finally:
        await container.dispose()


async def test_readiness_is_200_ready_when_the_real_database_answers(
    test_database_url: URL,
) -> None:
    """실제 DB가 응답하면 준비 확인은 200 ready다.

    테스트 코드: PL-028
    """
    # given: 마이그레이션이 적용된 임시 PostgreSQL의 접속 주소
    url = test_database_url.render_as_string(hide_password=False)
    # when: GET /readyz (전제: 그 주소에 연결된 실제 Container)
    response = await _readyz(url)
    # then: 200 {"status": "ready"}
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_readiness_does_not_log_sql_at_info(
    test_database_url: URL, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="sqlalchemy.engine")
    url = test_database_url.render_as_string(hide_password=False)
    caplog.clear()

    response = await _readyz(url, db_echo=True)

    assert response.status_code == 200
    assert not any(
        record.name.startswith("sqlalchemy.engine") and record.levelno == logging.INFO
        for record in caplog.records
    )


async def test_readiness_is_503_without_leaking_the_cause_when_the_database_is_down() -> None:
    """DB에 접속할 수 없으면 준비 확인은 503이고 접속 정보를 감춘다.

    테스트 코드: PL-029
    """
    # when: GET /readyz (전제: 닫힌 포트를 가리키는 접속 주소(비밀번호 포함)로 만든 실제 Container)
    response = await _readyz(UNREACHABLE_DB_URL)
    # then: 503 not-ready Problem이고 비밀번호·postgresql·호스트 주소가 응답에 없다
    assert response.status_code == 503
    assert response.json()["type"] == f"{PROBLEM_PREFIX}not-ready"
    for token in (UNREACHABLE_DB_PASSWORD, "postgresql", "127.0.0.1"):
        assert token not in response.text
