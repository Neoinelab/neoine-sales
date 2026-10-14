"""GET /users?status=active|resigned|all 와 재등록(AC7·9, T20·T23)."""

from typing import TYPE_CHECKING

import pytest

from app.domain.auth.principal import Role
from tests.e2e.payloads_auth import USERS, problem_type
from tests.factories_auth import make_user

if TYPE_CHECKING:
    from httpx import AsyncClient

    from tests.fakes.use_cases import FakeUseCases


async def _items(client: AsyncClient, **params: str) -> list[dict[str, object]]:
    response = await client.get(USERS, params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, object]] = response.json()["items"]
    return items


async def _resigned_kim(use_cases: FakeUseCases) -> str:
    await use_cases.seed_user("kim", Role.SALES)
    kim = await use_cases.user_id_of("kim")
    await use_cases.resign_user(kim)
    return str(kim)


async def test_status_defaults_to_active_and_hides_resigned_users(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _resigned_kim(use_cases)
    await use_cases.seed_user("lee", Role.USER)

    assert [i["login_id"] for i in await _items(admin_client)] == ["root", "lee"]
    assert [i["login_id"] for i in await _items(admin_client, status="active")] == ["root", "lee"]


async def test_status_resigned_lists_only_resigned_users_with_time_and_reason(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    kim_id = await _resigned_kim(use_cases)

    (kim,) = await _items(admin_client, status="resigned")

    assert kim["id"] == kim_id
    assert kim["status"] == "resigned"
    assert kim["delete_reason"] == "resigned"
    assert str(kim["deleted_at"]).startswith("2026-01-01T09:")


async def test_status_all_lists_everyone_in_creation_order(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _resigned_kim(use_cases)
    await use_cases.seed_user("lee", Role.USER)

    items = await _items(admin_client, status="all")

    assert [(i["login_id"], i["status"]) for i in items] == [
        ("root", "active"),
        ("kim", "resigned"),
        ("lee", "active"),
    ]
    assert items[0]["deleted_at"] is None
    assert items[0]["delete_reason"] is None


@pytest.mark.parametrize("status", ["", "ALL", "deleted", "retired", "1"])
async def test_invalid_status_is_422_request_validation(
    admin_client: AsyncClient, status: str
) -> None:
    response = await admin_client.get(USERS, params={"status": status})

    assert response.status_code == 422
    assert problem_type(response.json()) == "request-validation"


async def test_status_all_paginates(admin_client: AsyncClient, use_cases: FakeUseCases) -> None:
    await _resigned_kim(use_cases)
    await use_cases.seed_user("lee", Role.USER)

    page = await _items(admin_client, status="all", offset="1", limit="1")

    assert [i["login_id"] for i in page] == ["kim"]


async def test_registering_a_resigned_login_id_again_creates_a_new_row(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    old_id = await _resigned_kim(use_cases)

    response = await admin_client.post(USERS, json={"login_id": "kim", "role": "user"})

    assert response.status_code == 201
    assert response.json()["id"] != old_id
    assert response.json()["status"] == "active"
    both = [i for i in await _items(admin_client, status="all") if i["login_id"] == "kim"]
    assert [(i["id"] == old_id, i["status"]) for i in both] == [
        (True, "resigned"),
        (False, "active"),
    ]
    assert [i["login_id"] for i in await _items(admin_client)] == ["root", "kim"]


async def test_registering_a_login_id_that_is_active_again_is_409_even_with_resigned_rows(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await _resigned_kim(use_cases)
    assert (
        await admin_client.post(USERS, json={"login_id": "kim", "role": "user"})
    ).status_code == 201

    again = await admin_client.post(USERS, json={"login_id": "KIM", "role": "sales"})

    assert again.status_code == 409
    assert problem_type(again.json()) == "already-exists"
    kims = [i for i in await _items(admin_client, status="all") if i["login_id"] == "kim"]
    assert len(kims) == 2  # 퇴사 행 하나 + 재직 행 하나


async def test_a_user_registered_by_a_resigned_admin_shows_the_creator_as_resigned(
    admin_client: AsyncClient, use_cases: FakeUseCases
) -> None:
    await use_cases.seed_user("boss", Role.ADMIN)
    boss = await use_cases.user_id_of("boss")
    async with use_cases.uow as uow:  # boss가 등록한 사용자
        await uow.users.add(make_user("newbie", created_by_user_id=boss))
        await uow.commit()
    await use_cases.resign_user(boss)

    newbie = next(i for i in await _items(admin_client) if i["login_id"] == "newbie")

    assert newbie["created_by"]["label"] == "boss(퇴사)"  # type: ignore[index]
    assert newbie["created_by"]["resigned"] is True  # type: ignore[index]
