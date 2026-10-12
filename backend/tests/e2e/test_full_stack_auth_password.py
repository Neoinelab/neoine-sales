"""AUTH-7·T-P17: 로그인·2단계 설정 뒤 4개 테이블에 비밀번호와 원본 아이디/IP가 없다."""

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.e2e.conftest import AuthFullStack, new_client
from tests.e2e.payloads_auth import LOGIN, SETUP, SETUP_DIRECTORY, credentials, directory_payload
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration
TABLES = ("users", "login_failures", "directory_settings", "auth_sessions")


async def _dump(engine: AsyncEngine) -> dict[str, str]:
    dumped: dict[str, str] = {}
    async with engine.connect() as connection:
        for table in TABLES:
            rows = await connection.execute(text(f"select t::text from {table} t"))  # noqa: S608
            dumped[table] = "\n".join(row[0] for row in rows)
    return dumped


async def test_auth_flows_leave_no_password_in_any_table(auth_full_stack: AuthFullStack) -> None:
    wrong = DUMMY_PASSWORD + "-wrong"
    auth_full_stack.directory.add_account("kim", DUMMY_PASSWORD)
    container, app = auth_full_stack.open_app()
    engine = create_async_engine(auth_full_stack.database_url, poolclass=NullPool)
    try:
        async with new_client(app) as http:
            await http.put(SETUP_DIRECTORY, json=directory_payload())
            await http.post(SETUP, json=credentials("kim", wrong))
            await http.post(SETUP, json=credentials("kim", DUMMY_PASSWORD))
            await http.post(LOGIN, json=credentials("kim", wrong))
            await http.post(LOGIN, json=credentials("kim", DUMMY_PASSWORD))

        dumped = await _dump(engine)
    finally:
        await engine.dispose()
        await container.dispose()

    assert dumped["users"], "사용자가 등록되지 않아 검사가 의미 없다"
    assert dumped["login_failures"], "실패 카운터가 남지 않아 검사가 의미 없다"
    for table, content in dumped.items():
        assert DUMMY_PASSWORD not in content, table
        assert wrong not in content, table
    assert "kim" not in dumped["login_failures"]
    assert "127.0.0.1" not in dumped["login_failures"]
