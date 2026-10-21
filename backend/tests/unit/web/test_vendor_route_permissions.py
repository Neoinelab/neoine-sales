"""Vendor 라우터의 권한(AC-7): 읽기는 모든 역할, 쓰기는 admin만(403), 미로그인은 401."""

import pytest

from app.domain.auth.principal import Role
from app.web.permissions import ADMIN_DENIED
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import new_id
from tests.unit.web.vendor_http import URL, client_for, make_solution, make_vendor, problem


def _writes(vendor_id: object, solution_id: object) -> list[tuple[str, str, dict[str, str] | None]]:
    return [
        ("POST", URL, {"name": "X"}),
        ("PATCH", f"{URL}/{vendor_id}", {"name": "X"}),
        ("DELETE", f"{URL}/{vendor_id}", None),
        ("POST", f"{URL}/{vendor_id}/solutions", {"name": "X"}),
        ("PATCH", f"{URL}/{vendor_id}/solutions/{solution_id}", {"name": "X"}),
        ("DELETE", f"{URL}/{vendor_id}/solutions/{solution_id}", None),
    ]


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_sales_and_user_cannot_change_vendors_and_nothing_is_saved(role: Role) -> None:
    use_cases = FakeUseCases()
    async with client_for(use_cases) as admin:
        vendor = await make_vendor(admin)
        solution = await make_solution(admin, vendor["id"], "Cloud")
    async with client_for(use_cases, role=role) as http:
        responses = [
            await http.request(method, url, json=body)
            for method, url, body in _writes(vendor["id"], solution["id"])
        ]
        listed = (await http.get(URL)).json()

    for response in responses:
        problem(response, 403, "forbidden")
    assert [(v["name"], [s["name"] for s in v["solutions"]]) for v in listed] == [
        ("SAP", ["Cloud"])
    ]


async def test_sales_gets_the_admin_required_message() -> None:
    async with client_for(FakeUseCases(), role=Role.SALES) as http:
        response = await http.post(URL, json={"name": "X"})

    assert problem(response, 403, "forbidden")["detail"] == ADMIN_DENIED


async def test_unauthenticated_requests_are_401() -> None:
    async with client_for(FakeUseCases(), role=None) as http:
        responses = [await http.get(URL)]
        for method, url, body in _writes(new_id(), new_id()):
            responses.append(await http.request(method, url, json=body))

    for response in responses:
        problem(response, 401, "unauthenticated")
