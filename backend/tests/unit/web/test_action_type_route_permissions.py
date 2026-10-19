"""Action 유형 라우터의 권한(AC-1·2·6): 조회는 모든 역할, 생성은 sales·admin, 변경·삭제 admin."""

from uuid import uuid4

import pytest

from app.domain.auth.principal import Role
from app.web.permissions import ADMIN_DENIED
from tests.unit.web.action_type_http import URL, seeded_use_cases, type_id_of
from tests.unit.web.vendor_http import client_for, problem


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_may_list_action_types(role: Role) -> None:
    async with client_for(seeded_use_cases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 8


async def test_user_cannot_create_a_type_and_nothing_is_saved() -> None:
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.USER) as http:
        response = await http.post(URL, json={"name": "웨비나"})
        listed = (await http.get(URL)).json()

    assert response.status_code == 403, response.text
    assert "웨비나" not in [item["name"] for item in listed]


async def test_sales_cannot_rename_or_delete_and_gets_the_admin_required_message() -> None:
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.SALES) as http:
        demo = await type_id_of(http, "데모")
        renamed = await http.patch(f"{URL}/{demo}", json={"name": "시연"})
        deleted = await http.delete(f"{URL}/{demo}")
        listed = (await http.get(URL)).json()

    assert problem(renamed, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert problem(deleted, 403, "forbidden")["detail"] == ADMIN_DENIED
    assert "데모" in [item["name"] for item in listed]


async def test_user_cannot_rename_or_delete() -> None:
    use_cases = seeded_use_cases()
    async with client_for(use_cases, role=Role.USER) as http:
        demo = await type_id_of(http, "데모")
        renamed = await http.patch(f"{URL}/{demo}", json={"name": "시연"})
        deleted = await http.delete(f"{URL}/{demo}")

    assert renamed.status_code == 403, renamed.text
    assert deleted.status_code == 403, deleted.text


async def test_the_permission_is_checked_before_the_id_is_looked_up() -> None:
    async with client_for(seeded_use_cases(), role=Role.SALES) as http:
        renamed = await http.patch(f"{URL}/{uuid4()}", json={"name": "x"})
        deleted = await http.delete(f"{URL}/{uuid4()}")

    problem(renamed, 403, "forbidden")
    problem(deleted, 403, "forbidden")


async def test_unauthenticated_requests_are_401() -> None:
    async with client_for(seeded_use_cases(), role=None) as http:
        responses = [
            await http.get(URL),
            await http.post(URL, json={"name": "x"}),
            await http.patch(f"{URL}/{uuid4()}", json={"name": "x"}),
            await http.delete(f"{URL}/{uuid4()}"),
        ]

    for response in responses:
        problem(response, 401, "unauthenticated")
