"""사용자 관리 전 구간(PostgreSQL + 가짜 디렉터리): 삭제 즉시 차단, 마지막 admin, 삭제 경쟁."""

import asyncio
from typing import TYPE_CHECKING

import pytest

from tests.e2e.admin_flow import bootstrap_admin
from tests.e2e.conftest import new_client
from tests.e2e.payloads_auth import LOGIN, ME, USERS, credentials, problem_type

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.e2e.conftest import AuthFullStack

pytestmark = pytest.mark.integration
CUSTOMERS = "/api/v1/customers"


async def _id_of(client: AsyncClient, login_id: str) -> str:
    items = (await client.get(USERS)).json()["items"]
    return str(next(i["id"] for i in items if i["login_id"] == login_id))


async def test_registered_user_logs_in_and_deleted_user_is_blocked_at_once(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim", display_name="김영업")
    container, app, admin = await bootstrap_admin(auth_full_stack)
    try:
        created = await admin.post(USERS, json={"login_id": "kim", "role": "sales"})
        assert created.status_code == 201
        async with new_client(app) as kim:
            assert (await kim.post(LOGIN, json=credentials())).status_code == 200
            assert (await kim.get(CUSTOMERS)).status_code == 200
            assert (await admin.get(USERS)).json()["items"][1]["last_login_at"] is not None

            deleted = await admin.delete(f"{USERS}/{created.json()['id']}")

            assert deleted.status_code == 200
            assert deleted.json() == {"outcome": "deleted"}  # kim을 가리키는 행이 없다
            assert (await kim.get(CUSTOMERS)).status_code == 401
            assert (await kim.get(ME)).status_code == 401
            assert (await kim.post(LOGIN, json=credentials())).status_code == 401
    finally:
        await admin.aclose()
        await container.dispose()


async def test_old_session_stays_dead_after_the_same_login_id_is_registered_again(
    auth_full_stack: AuthFullStack,
) -> None:
    auth_full_stack.directory.add_account("kim", "pw-kim")
    container, app, admin = await bootstrap_admin(auth_full_stack)
    try:
        created = await admin.post(USERS, json={"login_id": "kim", "role": "sales"})
        async with new_client(app) as old_session:
            await old_session.post(LOGIN, json=credentials())
            await admin.delete(f"{USERS}/{created.json()['id']}")
            again = await admin.post(USERS, json={"login_id": "kim", "role": "sales"})
            assert again.status_code == 201

            assert (await old_session.get(CUSTOMERS)).status_code == 401
            assert (await old_session.post(LOGIN, json=credentials())).status_code == 200
    finally:
        await admin.aclose()
        await container.dispose()


async def test_duplicate_login_id_is_409_and_a_deleted_one_can_return(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    try:
        first = await admin.post(USERS, json={"login_id": "kim", "role": "user"})
        duplicate = await admin.post(USERS, json={"login_id": "KIM", "role": "user"})
        await admin.delete(f"{USERS}/{first.json()['id']}")
        returned = await admin.post(USERS, json={"login_id": "kim", "role": "user"})

        assert (first.status_code, duplicate.status_code, returned.status_code) == (201, 409, 201)
        assert problem_type(duplicate.json()) == "already-exists"
    finally:
        await admin.aclose()
        await container.dispose()


async def test_the_only_admin_cannot_be_deleted_or_delete_themselves(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    try:
        response = await admin.delete(f"{USERS}/{await _id_of(admin, 'root')}")

        assert response.status_code == 409
        assert problem_type(response.json()) == "invalid-state"
        assert (await admin.get(ME)).status_code == 200
    finally:
        await admin.aclose()
        await container.dispose()


async def test_two_admins_deleting_each_other_at_once_leave_exactly_one_admin(
    auth_full_stack: AuthFullStack,
) -> None:
    container, app, first = await bootstrap_admin(auth_full_stack)
    try:
        created = await first.post(USERS, json={"login_id": "boss", "role": "admin"})
        auth_full_stack.directory.add_account("boss", "pw-boss")
        async with new_client(app) as second:
            assert (
                await second.post(LOGIN, json=credentials("boss", "pw-boss"))
            ).status_code == 200
            root_id = await _id_of(first, "root")

            results = await asyncio.gather(
                first.delete(f"{USERS}/{created.json()['id']}"),
                second.delete(f"{USERS}/{root_id}"),
            )

            statuses = [r.status_code for r in results]
            assert statuses.count(200) == 1, statuses
            loser = next(r for r in results if r.status_code != 200)
            # 진 쪽은 마지막 admin 보호(409)이거나, 이긴 쪽이 이미 요청자를 삭제해 401이다.
            assert loser.status_code in {401, 409}, statuses
            if loser.status_code == 409:
                assert problem_type(loser.json()) == "invalid-state"
            # first가 boss를 지웠다면(200) 생존자는 first(root), 아니면 second(boss)다.
            survivor = first if results[0].status_code == 200 else second
            items = (await survivor.get(USERS)).json()["items"]
            assert [i["role"] for i in items] == ["admin"]
    finally:
        await first.aclose()
        await container.dispose()


async def test_deleting_a_user_while_first_admin_setup_is_closed_does_not_reopen_setup(
    auth_full_stack: AuthFullStack,
) -> None:
    container, _app, admin = await bootstrap_admin(auth_full_stack)
    try:
        created = await admin.post(USERS, json={"login_id": "kim", "role": "user"})
        await admin.delete(f"{USERS}/{created.json()['id']}")

        config = (await admin.get("/api/v1/auth/config")).json()

        assert (config["needs_directory_setup"], config["needs_admin_setup"]) == (False, False)
    finally:
        await admin.aclose()
        await container.dispose()
