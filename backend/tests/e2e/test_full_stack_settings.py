"""AD 설정 관리 전 구간(PostgreSQL + 가짜 디렉터리): 잠금 경쟁, 세션 유지, 비밀번호 비저장."""

import asyncio
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.e2e.admin_flow import bootstrap_admin
from tests.e2e.conftest import new_client
from tests.e2e.payloads_auth import (
    CONFIG,
    LOGIN,
    ME,
    SETTINGS,
    SETTINGS_TEST,
    credentials,
    problem_type,
    settings_test_payload,
    settings_update_payload,
)
from tests.support.auth_seed import DUMMY_PASSWORD

if TYPE_CHECKING:
    from tests.e2e.conftest import AuthFullStack

pytestmark = pytest.mark.integration
NEW_DN = "dc=new,dc=test"
TABLES = ("users", "login_failures", "directory_settings", "auth_sessions")


async def test_admin_updates_settings_on_postgres_and_other_sessions_survive(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim")
    container, app, admin = await bootstrap_admin(auth_full_stack)
    try:
        await admin.post("/api/v1/users", json={"login_id": "kim", "role": "sales"})
        async with new_client(app) as kim:
            await kim.post(LOGIN, json=credentials())

            saved = await admin.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))

            assert saved.status_code == 200
            assert saved.json()["revision"] == 2
            me = (await admin.get(ME)).json()
            assert saved.json()["updated_by"]["id"] == me["user_id"]
            assert saved.json()["updated_by"]["name"] == "관리자"  # 로그인 때 저장된 표시 이름
            assert "login_id" not in saved.json()["updated_by"]
            assert (await admin.get(SETTINGS)).json() == saved.json()
            assert (await kim.get(ME)).status_code == 200
            assert (await admin.get(CONFIG)).json()["directory_login"] is True
    finally:
        await admin.aclose()
        await container.dispose()


async def test_settings_are_read_from_the_database_by_every_app_instance(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    other_container, other_app = auth_full_stack.open_app()
    try:
        await admin.put(SETTINGS, json=settings_update_payload(base_dn=NEW_DN))
        token = admin.cookies["neoine_session"]
        async with new_client(other_app, token=token) as elsewhere:
            body = (await elsewhere.get(SETTINGS)).json()

        assert (body["base_dn"], body["revision"]) == (NEW_DN, 2)
    finally:
        await admin.aclose()
        await container.dispose()
        await other_container.dispose()


async def test_two_saves_with_the_same_revision_commit_exactly_one(
    auth_full_stack: AuthFullStack,
) -> None:
    container, app, first = await bootstrap_admin(auth_full_stack)
    barrier = asyncio.Barrier(2)

    async def both_verified_before_either_saves() -> None:
        await asyncio.wait_for(barrier.wait(), timeout=10)

    try:
        async with new_client(app, token=first.cookies["neoine_session"]) as second:
            auth_full_stack.directory.on_authenticate = both_verified_before_either_saves

            results = await asyncio.gather(
                first.put(SETTINGS, json=settings_update_payload(base_dn="dc=one,dc=t")),
                second.put(SETTINGS, json=settings_update_payload(base_dn="dc=two,dc=t")),
            )

            assert sorted(r.status_code for r in results) == [200, 409]
            winner = next(r for r in results if r.status_code == 200)
            loser = next(r for r in results if r.status_code == 409)
            assert problem_type(loser.json()) == "invalid-state"
            auth_full_stack.directory.on_authenticate = None
            stored = (await first.get(SETTINGS)).json()
            assert (stored["revision"], stored["base_dn"]) == (2, winner.json()["base_dn"])
    finally:
        await first.aclose()
        await container.dispose()


async def test_a_stale_revision_is_rejected_by_the_database_row(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    try:
        await admin.put(SETTINGS, json=settings_update_payload(1, base_dn="dc=a,dc=t"))

        stale = await admin.put(SETTINGS, json=settings_update_payload(1, base_dn="dc=b,dc=t"))

        assert stale.status_code == 409
        assert (await admin.get(SETTINGS)).json()["base_dn"] == "dc=a,dc=t"
    finally:
        await admin.aclose()
        await container.dispose()


async def test_test_endpoint_leaves_the_stored_row_untouched(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    try:
        before = (await admin.get(SETTINGS)).json()

        result = await admin.post(SETTINGS_TEST, json=settings_test_payload(base_dn=NEW_DN))

        assert result.json()["success"] is True
        assert (await admin.get(SETTINGS)).json() == before
    finally:
        await admin.aclose()
        await container.dispose()


async def test_settings_changes_leave_no_password_in_any_table(
    auth_full_stack: AuthFullStack,
) -> None:
    wrong = DUMMY_PASSWORD + "-wrong"
    container, _app, admin = await bootstrap_admin(auth_full_stack, "root", DUMMY_PASSWORD)
    engine = create_async_engine(auth_full_stack.database_url, poolclass=NullPool)
    try:
        await admin.put(SETTINGS, json=settings_update_payload(1, wrong, base_dn=NEW_DN))
        await admin.put(SETTINGS, json=settings_update_payload(1, DUMMY_PASSWORD, base_dn=NEW_DN))
        await admin.post(SETTINGS_TEST, json=settings_test_payload(wrong))
        await admin.post(SETTINGS_TEST, json=settings_test_payload(DUMMY_PASSWORD))
        dumped: dict[str, str] = {}
        async with engine.connect() as connection:
            for table in TABLES:
                rows = await connection.execute(text(f"select t::text from {table} t"))  # noqa: S608
                dumped[table] = "\n".join(row[0] for row in rows)
    finally:
        await engine.dispose()
        await admin.aclose()
        await container.dispose()

    assert NEW_DN in dumped["directory_settings"], "저장이 일어나지 않아 검사가 의미 없다"
    assert dumped["login_failures"], "실패 카운터가 남지 않아 검사가 의미 없다"
    for table, content in dumped.items():
        assert DUMMY_PASSWORD not in content, table
        assert wrong not in content, table
    assert "root" not in dumped["login_failures"]
