"""사용자 삭제 API (AC3~5, 9): 연결이 없으면 물리 삭제, 있으면 퇴사 처리. 즉시 차단, 보호 규칙.

DELETE /users/{id}는 200과 `{"outcome": "deleted" | "resigned"}`를 돌려준다(204가 아니다).
이미 퇴사한 사용자의 재삭제는 409, 물리 삭제된 사용자의 재삭제는 404.
"""

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client
from tests.e2e.payloads_auth import ME, USERS, credentials, problem_type
from tests.support.user_links import LINK_KINDS, link_user

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"
BUSINESS_READ = "/api/v1/customers"
LOGIN = "/api/v1/auth/login"


async def _id_of(client: AsyncClient, login_id: str, status: str = "active") -> str:
    items = (await client.get(USERS, params={"status": status})).json()["items"]
    return str(next(i["id"] for i in items if i["login_id"] == login_id))


async def _link(use_cases: FakeUseCases, login_id: str, kind: str = "deal_owner") -> None:
    user = await use_cases.seed_user(login_id, Role.SALES)
    await link_user(lambda: use_cases.uow, user, kind)


async def test_delete_without_links_returns_200_deleted_and_removes_the_user(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    assert response.status_code == 200
    assert response.json() == {"outcome": "deleted"}
    all_users = (await admin_client.get(USERS, params={"status": "all"})).json()["items"]
    assert [i["login_id"] for i in all_users] == ["root"]


@pytest.mark.parametrize("kind", LINK_KINDS)
async def test_delete_with_any_reference_returns_200_resigned_and_keeps_the_row(
    admin_client: AsyncClient, use_cases: FakeUseCases, kind: str
) -> None:
    await _link(use_cases, "kim", kind)

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    assert response.status_code == 200
    assert response.json() == {"outcome": "resigned"}
    resigned = (await admin_client.get(USERS, params={"status": "resigned"})).json()["items"]
    (kim,) = [i for i in resigned if i["login_id"] == "kim"]
    assert kim["status"] == "resigned"
    assert kim["delete_reason"] == "resigned"
    assert kim["deleted_at"].startswith("2026-01-01T09:00:")


async def test_delete_accepts_the_reason_query_and_rejects_unknown_reasons(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    await use_cases.seed_user("lee", Role.SALES)

    ok = await admin_client.delete(
        f"{USERS}/{await _id_of(admin_client, 'kim')}", params={"reason": "resigned"}
    )
    bad = await admin_client.delete(
        f"{USERS}/{await _id_of(admin_client, 'lee')}", params={"reason": "fired"}
    )

    assert ok.status_code == 200
    assert bad.status_code == 422
    assert problem_type(bad.json()) == "request-validation"
    assert await _id_of(admin_client, "lee")


@pytest.mark.parametrize("linked", [False, True])
async def test_deleted_or_resigned_users_existing_session_is_rejected_from_the_next_request(
    admin_client: AsyncClient,
    client_as: Callable[[str, Role], Awaitable[AsyncClient]],
    use_cases: FakeUseCases,
    linked: bool,
) -> None:
    kim = await client_as("kim", Role.SALES)
    assert (await kim.get(BUSINESS_READ)).status_code == 200
    if linked:
        user = next(u for u in await _users(use_cases) if u.login_id.value == "kim")
        await link_user(lambda: use_cases.uow, user, "deal_owner")

    await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    assert (await kim.get(BUSINESS_READ)).status_code == 401
    assert (await kim.get(ME)).status_code == 401


async def _users(use_cases: FakeUseCases) -> list:  # type: ignore[type-arg]
    async with use_cases.uow as uow:
        return list(await uow.users.list_users(limit=100))


async def test_a_resigned_user_cannot_log_in_with_a_valid_ad_password(
    admin_client: AsyncClient, use_cases: FakeUseCases, anonymous_client: AsyncClient
) -> None:
    await _link(use_cases, "kim")
    use_cases.directory.add_account("kim", "pw-kim")
    before = await anonymous_client.post(LOGIN, json=credentials("kim", "pw-kim"))
    await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    after = await anonymous_client.post(LOGIN, json=credentials("kim", "pw-kim"))

    assert before.status_code == 200
    assert after.status_code == 401
    assert problem_type(after.json()) == "unauthenticated"


async def test_deleting_a_resigned_user_again_is_409_invalid_state(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _link(use_cases, "kim")
    target = f"{USERS}/{await _id_of(admin_client, 'kim')}"
    assert (await admin_client.delete(target)).status_code == 200

    response = await admin_client.delete(target)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(response.json()) == "invalid-state"
    assert "퇴사" in response.json()["detail"]


async def test_deleting_a_physically_deleted_user_again_is_404_not_found(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    target = f"{USERS}/{await _id_of(admin_client, 'kim')}"
    assert (await admin_client.delete(target)).status_code == 200

    response = await admin_client.delete(target)

    assert response.status_code == 404
    assert problem_type(response.json()) == "not-found"


async def test_delete_user_with_an_unknown_id_is_404_not_found(admin_client: AsyncClient) -> None:
    response = await admin_client.delete(f"{USERS}/{uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(response.json()) == "not-found"


async def test_delete_user_with_a_malformed_id_is_422(admin_client: AsyncClient) -> None:
    response = await admin_client.delete(f"{USERS}/not-a-uuid")

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


@pytest.mark.parametrize("linked", [False, True])
async def test_an_admin_cannot_delete_themselves_whether_or_not_the_row_is_linked(
    admin_client: AsyncClient, use_cases: FakeUseCases, linked: bool
) -> None:
    await use_cases.seed_user(
        "boss", Role.ADMIN
    )  # 마지막 admin 규칙이 아니라 자기 삭제 규칙을 본다
    if linked:
        root = next(u for u in await _users(use_cases) if u.login_id.value == "root")
        await link_user(lambda: use_cases.uow, root, "deal_owner")

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'root')}")

    assert response.status_code == 409
    assert problem_type(response.json()) == "invalid-state"
    assert "자기 자신" in response.json()["detail"]
    assert (await admin_client.get(ME)).status_code == 200


async def test_an_admin_can_delete_another_admin_while_two_exist(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("boss", Role.ADMIN)

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'boss')}")

    assert response.status_code == 200


async def test_a_resigned_user_disappears_from_the_default_list(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _link(use_cases, "boss")

    resigned = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'boss')}")
    default_list = await admin_client.get(USERS)

    assert resigned.json() == {"outcome": "resigned"}
    assert [i["login_id"] for i in default_list.json()["items"]] == ["root"]


async def test_a_dev_login_admin_is_a_regular_user_row_that_can_manage_users(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    issued = await use_cases.dev_login().execute(Role.ADMIN)
    async with new_client(app, token=issued.token) as dev_admin:
        created = await dev_admin.post(USERS, json={"login_id": "new", "role": "user"})
        removed = await dev_admin.delete(f"{USERS}/{await _id_of(dev_admin, 'kim')}")
        me = (await dev_admin.get(ME)).json()
        listed = (await dev_admin.get(USERS)).json()["items"]

    assert created.status_code == 201
    assert created.json()["created_by"]["name"] == "개발 사용자(admin)"
    assert "login_id" not in created.json()["created_by"]
    assert created.json()["created_by"]["id"] == me["user_id"]
    assert removed.status_code == 200
    assert "dev-admin" in [i["login_id"] for i in listed]
