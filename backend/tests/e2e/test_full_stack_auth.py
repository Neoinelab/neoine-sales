"""인증 전 구간 통합(PostgreSQL + 가짜 디렉터리): 2단계 설정, 로그인, 삭제 차단, 공유 카운터."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.e2e.conftest import SESSION_COOKIE, AuthFullStack, new_client
from tests.e2e.payloads_auth import (
    CONFIG,
    LOGIN,
    ME,
    SETUP,
    SETUP_DIRECTORY,
    credentials,
    directory_payload,
    problem_type,
)
from tests.fakes.auth_stack import MAX_PER_ACCOUNT

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.integration
LOGOUT = "/api/v1/auth/logout"


async def _flags(client: AsyncClient) -> tuple[bool, bool]:
    body = (await client.get(CONFIG)).json()
    return body["needs_directory_setup"], body["needs_admin_setup"]


async def _sql(auth_full_stack: AuthFullStack, statement: str) -> None:
    engine = create_async_engine(auth_full_stack.database_url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def test_setup_login_logout_flow_runs_on_postgres(auth_full_stack: AuthFullStack) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim", display_name="김관리", email="k@c.test")
    container, app = auth_full_stack.open_app()
    try:
        async with new_client(app) as http:
            assert await _flags(http) == (True, False)
            assert (await http.put(SETUP_DIRECTORY, json=directory_payload())).status_code == 200
            assert await _flags(http) == (False, True)
            done = await http.post(SETUP, json=credentials())
            assert done.status_code == 200
            assert (await http.get(ME)).json()["role"] == "admin"
            assert await _flags(http) == (False, False)
            assert (await http.post(LOGOUT)).status_code == 204
            assert (await http.get(ME)).status_code == 401

            again = await http.post(LOGIN, json=credentials())
            wrong = await http.post(LOGIN, json=credentials("kim", "wrong"))

            assert again.status_code == 200
            assert again.json()["name"] == "김관리"
            assert wrong.status_code == 401
            assert (await http.put(SETUP_DIRECTORY, json=directory_payload())).status_code == 409
    finally:
        await container.dispose()


async def test_concurrent_setup_requests_create_exactly_one_admin(
    auth_full_stack: AuthFullStack,
) -> None:
    directory = auth_full_stack.directory
    directory.add_account("kim", "pw-kim")
    directory.add_account("lee", "pw-lee")
    barrier = asyncio.Barrier(2)

    async def both_authenticated_before_either_registers() -> None:
        await asyncio.wait_for(barrier.wait(), timeout=10)

    container, app = auth_full_stack.open_app()
    try:
        async with new_client(app) as first, new_client(app) as second:
            await first.put(SETUP_DIRECTORY, json=directory_payload())
            directory.on_authenticate = both_authenticated_before_either_registers

            responses = await asyncio.gather(
                first.post(SETUP, json=credentials("kim", "pw-kim")),
                second.post(SETUP, json=credentials("lee", "pw-lee")),
            )

            statuses = sorted(r.status_code for r in responses)
            assert statuses == [200, 409]
            loser = next(r for r in responses if r.status_code == 409)
            assert problem_type(loser.json()) == "invalid-state"
            assert SESSION_COOKIE not in loser.headers.get("set-cookie", "")
            assert await _flags(first) == (False, False)
    finally:
        await container.dispose()


async def test_deleted_user_is_locked_out_on_the_next_request(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim")
    container, app = auth_full_stack.open_app()
    try:
        async with new_client(app) as http:
            await http.put(SETUP_DIRECTORY, json=directory_payload())
            await http.post(SETUP, json=credentials())
            assert (await http.get("/api/v1/customers")).status_code == 200

            await _sql(auth_full_stack, "delete from users where login_id='kim'")

            assert (await http.get("/api/v1/customers")).status_code == 401
            assert (await http.get(ME)).status_code == 401
            relogin = await http.post(LOGIN, json=credentials())
            assert relogin.status_code == 401
    finally:
        await container.dispose()


async def test_role_change_in_the_database_applies_to_existing_sessions(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim")
    container, app = auth_full_stack.open_app()
    try:
        async with new_client(app) as http:
            await http.put(SETUP_DIRECTORY, json=directory_payload())
            await http.post(SETUP, json=credentials())

            await _sql(auth_full_stack, "update users set role = 'user' where login_id='kim'")

            assert (await http.get(ME)).json()["role"] == "user"
    finally:
        await container.dispose()


async def test_failure_counter_is_shared_between_app_instances(
    auth_full_stack: AuthFullStack,
) -> None:
    directory = auth_full_stack.directory
    directory.add_account("kim", "pw-kim")
    first_container, first_app = auth_full_stack.open_app()
    second_container, second_app = auth_full_stack.open_app()
    try:
        async with new_client(first_app) as one, new_client(second_app) as two:
            await one.put(SETUP_DIRECTORY, json=directory_payload())
            await one.post(SETUP, json=credentials())
            await one.post(LOGOUT)
            for _ in range(MAX_PER_ACCOUNT):
                assert (await one.post(LOGIN, json=credentials("kim", "bad"))).status_code == 401
            calls_before = len(directory.authenticate_calls)

            blocked = await two.post(LOGIN, json=credentials())

            assert blocked.status_code == 429
            assert len(directory.authenticate_calls) == calls_before
    finally:
        await first_container.dispose()
        await second_container.dispose()


async def test_new_settings_apply_to_the_next_login_on_every_instance(
    auth_full_stack: AuthFullStack,
) -> None:
    directory = auth_full_stack.directory
    directory.add_account("kim", "pw-kim")
    first_container, first_app = auth_full_stack.open_app()
    second_container, second_app = auth_full_stack.open_app()
    try:
        async with new_client(first_app) as one, new_client(second_app) as two:
            await one.put(SETUP_DIRECTORY, json=directory_payload())
            await one.post(SETUP, json=credentials())
            await _sql(
                auth_full_stack,
                "update directory_settings set base_dn = 'dc=changed,dc=test', revision = 2",
            )

            assert (await two.post(LOGIN, json=credentials())).status_code == 200

            assert directory.authenticate_calls[-1].settings.base_dn == "dc=changed,dc=test"
    finally:
        await first_container.dispose()
        await second_container.dispose()


async def test_dev_session_works_only_while_dev_login_is_enabled(
    auth_full_stack: AuthFullStack,
) -> None:
    enabled_container, enabled_app = auth_full_stack.open_app(dev_login_enabled=True)
    disabled_container, disabled_app = auth_full_stack.open_app(dev_login_enabled=False)
    try:
        async with new_client(enabled_app) as http:
            issued = await http.post("/api/v1/auth/dev-login", json={"role": "admin"})
            token = issued.cookies[SESSION_COOKIE]
            assert (await http.get(ME)).json()["subject"] == "dev:admin"

        async with new_client(disabled_app, token=token) as http:
            assert (await http.get(ME)).status_code == 401
    finally:
        await enabled_container.dispose()
        await disabled_container.dispose()
