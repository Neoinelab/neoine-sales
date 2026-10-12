"""사용자 삭제 API (USER-4~7, T-E23~E25): 소프트 삭제, 즉시 차단, 마지막 admin·자기 삭제 금지."""

from typing import TYPE_CHECKING
from uuid import uuid4

from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client, principal_for
from tests.e2e.payloads_auth import ME, USERS, problem_type

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"
BUSINESS_READ = "/api/v1/customers"


async def _id_of(client: AsyncClient, login_id: str) -> str:
    items = (await client.get(USERS)).json()["items"]
    return str(next(i["id"] for i in items if i["login_id"] == login_id))


async def test_delete_user_returns_204_with_no_body_and_removes_the_user(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    assert response.status_code == 204
    assert response.content == b""
    assert [i["login_id"] for i in (await admin_client.get(USERS)).json()["items"]] == ["root"]


async def test_deleted_users_existing_session_is_rejected_from_the_next_request(
    admin_client: AsyncClient, client_as: Callable[[str, Role], Awaitable[AsyncClient]]
) -> None:
    kim = await client_as("kim", Role.SALES)
    assert (await kim.get(BUSINESS_READ)).status_code == 200

    await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")

    assert (await kim.get(BUSINESS_READ)).status_code == 401
    assert (await kim.get(ME)).status_code == 401


async def test_old_session_stays_dead_when_the_same_login_id_is_registered_again(
    admin_client: AsyncClient, client_as: Callable[[str, Role], Awaitable[AsyncClient]]
) -> None:
    kim = await client_as("kim", Role.SALES)
    await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'kim')}")
    await admin_client.post(USERS, json={"login_id": "kim", "role": "sales"})

    assert (await kim.get(ME)).status_code == 401


async def test_delete_user_with_an_unknown_id_is_404_not_found(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.delete(f"{USERS}/{uuid4()}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(response.json()) == "not-found"


async def test_delete_user_twice_is_404_the_second_time(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    target = f"{USERS}/{await _id_of(admin_client, 'kim')}"
    assert (await admin_client.delete(target)).status_code == 204

    response = await admin_client.delete(target)

    assert response.status_code == 404
    assert problem_type(response.json()) == "not-found"


async def test_delete_user_with_a_malformed_id_is_422(admin_client: AsyncClient) -> None:
    response = await admin_client.delete(f"{USERS}/not-a-uuid")

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


async def test_an_admin_cannot_delete_themselves(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user(
        "boss", Role.ADMIN
    )  # 마지막 admin 규칙이 아니라 자기 삭제 규칙을 본다

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'root')}")

    assert response.status_code == 409
    assert problem_type(response.json()) == "invalid-state"
    assert "자기 자신" in response.json()["detail"]
    assert (await admin_client.get(ME)).status_code == 200
    assert "root" in [i["login_id"] for i in (await admin_client.get(USERS)).json()["items"]]


async def test_the_last_admin_cannot_be_deleted(app: FastAPI, use_cases: FakeUseCases) -> None:
    await use_cases.seed_user("boss", Role.ADMIN)
    dev_token = await use_cases.issue_session_for(principal_for("dev:admin", Role.ADMIN))
    async with new_client(app, token=dev_token) as dev_admin:
        target = f"{USERS}/{await _id_of(dev_admin, 'boss')}"

        response = await dev_admin.delete(target)

        assert response.status_code == 409
        assert problem_type(response.json()) == "invalid-state"
        assert "마지막 관리자" in response.json()["detail"]
        assert await _id_of(dev_admin, "boss")


async def test_an_admin_can_delete_another_admin_while_two_exist(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("boss", Role.ADMIN)

    response = await admin_client.delete(f"{USERS}/{await _id_of(admin_client, 'boss')}")

    assert response.status_code == 204


async def test_a_dev_login_admin_without_a_users_row_can_manage_users(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    token = await use_cases.issue_session_for(principal_for("dev:admin", Role.ADMIN))
    async with new_client(app, token=token) as dev_admin:
        created = await dev_admin.post(USERS, json={"login_id": "new", "role": "user"})
        removed = await dev_admin.delete(f"{USERS}/{await _id_of(dev_admin, 'kim')}")

    assert created.status_code == 201
    assert created.json()["created_by"] == "dev:admin"
    assert removed.status_code == 204
