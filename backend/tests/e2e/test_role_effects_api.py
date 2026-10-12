"""역할은 세션이 아니라 users 표에서 매 요청 읽는다 (AUTH-10, ROLE-1~3, T-E33 보강)."""

from typing import TYPE_CHECKING

from app.domain.auth.credentials import LoginId
from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client, principal_for
from tests.e2e.payloads import customer_payload
from tests.e2e.payloads_auth import USERS, problem_type

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

CUSTOMERS = "/api/v1/customers"


async def _set_role(use_cases: FakeUseCases, login_id: str, role: Role) -> None:
    user = await use_cases.uow.users.get_active_by_login_id(LoginId(login_id))
    assert user is not None
    user.role = role
    await use_cases.uow.users.update(user)


async def test_a_demoted_admin_loses_admin_access_on_the_next_request(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], use_cases: FakeUseCases
) -> None:
    boss = await client_as("boss", Role.ADMIN)
    assert (await boss.get(USERS)).status_code == 200

    await _set_role(use_cases, "boss", Role.USER)

    assert (await boss.get(USERS)).status_code == 403
    assert (await boss.post(CUSTOMERS, json=customer_payload())).status_code == 403
    assert (await boss.get(CUSTOMERS)).status_code == 200


async def test_a_promoted_sales_user_gains_admin_access_on_the_next_request(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], use_cases: FakeUseCases
) -> None:
    kim = await client_as("kim", Role.SALES)
    assert (await kim.get(USERS)).status_code == 403

    await _set_role(use_cases, "kim", Role.ADMIN)

    assert (await kim.get(USERS)).status_code == 200


async def test_a_viewer_promoted_to_sales_can_write_immediately(
    client_as: Callable[[str, Role], Awaitable[AsyncClient]], use_cases: FakeUseCases
) -> None:
    lee = await client_as("lee", Role.USER)
    assert (await lee.post(CUSTOMERS, json=customer_payload())).status_code == 403

    await _set_role(use_cases, "lee", Role.SALES)

    assert (await lee.post(CUSTOMERS, json=customer_payload())).status_code == 201


async def test_the_role_written_into_the_session_is_ignored(
    app: FastAPI, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("sneaky", Role.USER)
    token = await use_cases.issue_session_for(principal_for("sneaky", Role.ADMIN))
    async with new_client(app, token=token) as http:
        users = await http.get(USERS)
        write = await http.post(CUSTOMERS, json=customer_payload())

    assert (users.status_code, write.status_code) == (403, 403)


async def test_a_role_changed_by_deleting_and_registering_again_applies_at_once(
    admin_client: AsyncClient, client_as: Callable[[str, Role], Awaitable[AsyncClient]]
) -> None:
    """수정 API가 없어 삭제 후 다른 역할로 재등록한다. 옛 세션은 폐기되어 다시 로그인해야 한다."""
    kim = await client_as("kim", Role.SALES)
    kim_id = next(
        i["id"] for i in (await admin_client.get(USERS)).json()["items"] if i["login_id"] == "kim"
    )
    await admin_client.delete(f"{USERS}/{kim_id}")
    await admin_client.post(USERS, json={"login_id": "kim", "role": "user"})

    assert (await kim.get(CUSTOMERS)).status_code == 401


async def test_forbidden_responses_are_problem_json_with_a_readable_detail(
    viewer_client: AsyncClient,
) -> None:
    response = await viewer_client.post(CUSTOMERS, json=customer_payload())

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert (body["status"], problem_type(body)) == (403, "forbidden")
    assert body["detail"].strip()
