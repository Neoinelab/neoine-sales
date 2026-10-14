"""사용자 관리 API 목록·등록 (USER-1~3·8, T-E20~E22). 접근 권한은 매트릭스 테스트가 고정한다."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.e2e.conftest import new_client
from tests.e2e.payloads_auth import USERS, problem_type

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases

PROBLEM = "application/problem+json"
USER_KEYS = {
    "id",
    "login_id",
    "role",
    "display_name",
    "email",
    "created_at",
    "created_by",
    "last_login_at",
    "status",
    "deleted_at",
    "delete_reason",
}
USER_REF_KEYS = {"id", "name", "resigned", "label"}  # 참조에는 AD 계정 아이디가 없다


async def _logins(client: AsyncClient) -> list[str]:
    return [item["login_id"] for item in (await client.get(USERS)).json()["items"]]


async def test_list_users_returns_the_documented_fields_without_any_password(
    admin_client: AsyncClient,
) -> None:
    response = await admin_client.get(USERS)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "offset", "limit"}
    (root,) = body["items"]
    assert set(root) == USER_KEYS
    assert (root["login_id"], root["role"]) == ("root", "admin")
    assert set(root["created_by"]) == USER_REF_KEYS
    assert root["created_by"]["name"] == "사용자 root"  # 최초 admin은 스스로 등록한 행(표시 이름)
    assert root["login_id"] == "root"  # 관리 화면용 목록 행은 AD 계정 아이디를 계속 보여준다
    assert root["created_by"]["id"] == root["id"]
    assert (root["status"], root["deleted_at"], root["delete_reason"]) == ("active", None, None)
    assert not any("password" in key.lower() for key in root)


async def test_list_users_shows_the_last_login_time_and_null_when_never_logged_in(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("fresh", Role.USER)

    items = {item["login_id"]: item for item in (await admin_client.get(USERS)).json()["items"]}

    assert items["root"]["last_login_at"].startswith("2026-01-01T09:00:")
    assert items["root"]["display_name"] == "사용자 root"
    assert items["fresh"]["last_login_at"] is None
    assert items["fresh"]["display_name"] is None


async def test_list_users_hides_deleted_users_and_keeps_creation_order(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("amy", Role.SALES)
    await use_cases.seed_user("bob", Role.USER)
    bob_id = next(
        i["id"] for i in (await admin_client.get(USERS)).json()["items"] if i["login_id"] == "bob"
    )
    assert (await admin_client.delete(f"{USERS}/{bob_id}")).status_code == 200

    assert await _logins(admin_client) == ["root", "amy"]


async def test_list_users_pages_with_offset_and_limit(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("amy", Role.SALES)
    await use_cases.seed_user("bob", Role.USER)

    body = (await admin_client.get(USERS, params={"offset": 1, "limit": 1})).json()

    assert [i["login_id"] for i in body["items"]] == ["amy"]
    assert (body["offset"], body["limit"]) == (1, 1)


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 201}, {"limit": "x"}])
async def test_list_users_rejects_invalid_paging(
    admin_client: AsyncClient, params: dict[str, object]
) -> None:
    response = await admin_client.get(USERS, params=params)  # type: ignore[arg-type]

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM)


@pytest.mark.parametrize("role", ["admin", "sales", "user"])
async def test_register_user_returns_201_with_the_chosen_role(
    admin_client: AsyncClient, role: str
) -> None:
    response = await admin_client.post(USERS, json={"login_id": "new.hire", "role": role})

    assert response.status_code == 201
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["login_id"], body["role"]) == ("new.hire", role)
    assert set(body["created_by"]) == USER_REF_KEYS
    assert (body["created_by"]["name"], body["created_by"]["label"]) == (
        "사용자 root",
        "사용자 root",
    )
    assert (body["status"], body["deleted_at"], body["delete_reason"]) == ("active", None, None)
    assert body["last_login_at"] is None
    assert body["created_at"].startswith("2026-01-01T09:00:")
    assert await _logins(admin_client) == ["root", "new.hire"]


async def test_register_user_normalizes_the_login_id(admin_client: AsyncClient) -> None:
    response = await admin_client.post(USERS, json={"login_id": "  Kim.Lee ", "role": "user"})

    assert response.status_code == 201
    assert response.json()["login_id"] == "kim.lee"


async def test_register_user_does_not_check_the_directory(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    response = await admin_client.post(USERS, json={"login_id": "not-in-ad", "role": "sales"})

    assert response.status_code == 201
    assert use_cases.directory.authenticate_calls == []
    assert use_cases.directory.probe_calls == []


@pytest.mark.parametrize("duplicate", ["root", "ROOT", " root "])
async def test_register_user_with_an_active_login_id_is_409_already_exists(
    admin_client: AsyncClient, duplicate: str
) -> None:
    response = await admin_client.post(USERS, json={"login_id": duplicate, "role": "user"})

    assert response.status_code == 409
    assert response.headers["content-type"].startswith(PROBLEM)
    assert problem_type(response.json()) == "already-exists"
    assert await _logins(admin_client) == ["root"]


async def test_register_user_again_after_a_physical_deletion_is_201(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("kim", Role.SALES)
    kim_id = next(
        i["id"] for i in (await admin_client.get(USERS)).json()["items"] if i["login_id"] == "kim"
    )
    await admin_client.delete(f"{USERS}/{kim_id}")

    response = await admin_client.post(USERS, json={"login_id": "kim", "role": "user"})

    assert response.status_code == 201
    assert response.json()["id"] != kim_id
    assert await _logins(admin_client) == ["root", "kim"]


@pytest.mark.parametrize("reserved", ["dev-admin", "dev-sales", "dev-user"])
async def test_register_user_with_a_reserved_dev_login_id_is_422(
    admin_client: AsyncClient, reserved: str
) -> None:
    response = await admin_client.post(USERS, json={"login_id": reserved, "role": "user"})

    assert response.status_code == 422
    assert problem_type(response.json()) == "invalid-value"
    assert await _logins(admin_client) == ["root"]


@pytest.mark.parametrize("login_id", ["", "   ", "-lead", ".lead", "a b", "한글", "a,b", "a=b"])
async def test_register_user_with_a_malformed_login_id_is_422_invalid_value(
    admin_client: AsyncClient, login_id: str
) -> None:
    response = await admin_client.post(USERS, json={"login_id": login_id, "role": "user"})

    assert response.status_code == 422
    assert problem_type(response.json()) == "invalid-value"
    assert await _logins(admin_client) == ["root"]


async def test_register_user_with_a_65_character_login_id_is_422(admin_client: AsyncClient) -> None:
    response = await admin_client.post(USERS, json={"login_id": "a" * 65, "role": "user"})

    assert response.status_code == 422
    assert problem_type(response.json()) in {"invalid-value", "request-validation"}
    assert await _logins(admin_client) == ["root"]


async def test_register_user_accepts_a_64_character_login_id(admin_client: AsyncClient) -> None:
    response = await admin_client.post(USERS, json={"login_id": "a" * 64, "role": "user"})

    assert response.status_code == 201


@pytest.mark.parametrize(
    "body",
    [
        {"login_id": "kim"},
        {"role": "user"},
        {"login_id": "kim", "role": "superuser"},
        {"login_id": "kim", "role": None},
        {"login_id": 7, "role": "user"},
        {"login_id": "kim", "role": "user", "password": "pw"},
        {"login_id": "kim", "role": "user", "display_name": "김"},
        {},
    ],
)
async def test_register_user_with_a_bad_body_is_422_request_validation(
    admin_client: AsyncClient, body: dict[str, object]
) -> None:
    response = await admin_client.post(USERS, json=body)

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"
    assert await _logins(admin_client) == ["root"]


@pytest.mark.parametrize("method", ["put", "patch", "get", "post"])
async def test_there_is_no_user_update_or_read_one_endpoint(
    admin_client: AsyncClient, method: str
) -> None:
    response = await admin_client.request(
        method, f"{USERS}/6f1c1b3a-0000-4000-8000-000000000001", json={"role": "admin"}
    )

    assert response.status_code == 405


async def test_register_and_delete_require_the_csrf_header(
    app: FastAPI,
    use_cases: FakeUseCases,
    client_as: Callable[[str, Role], Awaitable[AsyncClient]],
) -> None:
    admin = await client_as("root", Role.ADMIN)
    token = admin.cookies["neoine_session"]
    async with new_client(app, token=token, csrf=False) as bare:
        post = await bare.post(USERS, json={"login_id": "kim", "role": "user"})
        delete = await bare.delete(f"{USERS}/6f1c1b3a-0000-4000-8000-000000000001")

    assert (post.status_code, problem_type(post.json())) == (403, "csrf")
    assert (delete.status_code, problem_type(delete.json())) == (403, "csrf")
