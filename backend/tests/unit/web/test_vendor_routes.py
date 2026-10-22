"""Vendor 라우터(AC-1~4): FakeUseCases 위의 HTTP 계약, 문구, 권한(401·403).

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다. 실제 DB를 지나는 시나리오는
functional(admin/test_vendors.py)이 맡는다.
"""

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MISSING_ID
from tests.unit.web.vendor_http import (
    URL,
    VENDOR_KEYS,
    client_for,
    make_vendor,
    problem,
)

# ---- 생성·조회 (AC-1) ----


async def test_create_vendor_returns_201_with_location_and_the_documented_body() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json={"name": "  SAP  "})

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == VENDOR_KEYS
    assert (body["name"], body["usage_count"]) == ("SAP", 0)
    assert "solutions" not in body
    assert response.headers["location"] == f"{URL}/{body['id']}"


async def test_vendor_ids_are_json_integers() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http, "SAP")
        listed = (await http.get(URL)).json()

    assert type(vendor["id"]) is int
    assert type(listed[0]["id"]) is int


async def test_list_vendors_response_has_no_solutions_field() -> None:
    async with client_for(FakeUseCases()) as http:
        await make_vendor(http, "SAP")
        body = (await http.get(URL)).json()

    assert set(body[0]) == {"id", "name", "usage_count", "created_at", "updated_at"}
    assert set(body[0]) == VENDOR_KEYS


async def test_list_orders_vendors_by_lower_name() -> None:
    async with client_for(FakeUseCases()) as http:
        zeta = await make_vendor(http, "zeta")
        await make_vendor(http, "SAP")
        await make_vendor(http, "Alpha")
        body = (await http.get(URL)).json()

    assert [v["name"] for v in body] == ["Alpha", "SAP", "zeta"]
    assert zeta["id"] == body[2]["id"]


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_may_list_vendors(role: Role) -> None:
    async with client_for(FakeUseCases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == []


# ---- 이름 변경 (AC-3) ----


async def test_rename_vendor_returns_the_renamed_vendor() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP Korea"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "SAP Korea"
    assert set(response.json()) == VENDOR_KEYS


# ---- Solution 관리 API는 폐지됐다 (AC-2) ----


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/{vendor_id}/solutions", {"name": "Cloud"}),
        ("PATCH", "/{vendor_id}/solutions/2", {"name": "Cloud"}),
        ("DELETE", "/{vendor_id}/solutions/2", None),
    ],
)
async def test_solution_routes_are_not_found(
    method: str, path: str, body: dict[str, str] | None
) -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        response = await http.request(method, URL + path.format(vendor_id=vendor["id"]), json=body)
        listed = (await http.get(URL)).json()

    assert response.status_code == 404, response.text
    assert [v["name"] for v in listed] == ["SAP"]


# ---- 이름 규칙 (AC-3) ----


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("   ", "Vendor 이름을 입력하세요."),
        ("a" * 101, "Vendor 이름은 100자 이내로 입력하세요."),
    ],
)
async def test_invalid_vendor_names_are_422_with_the_domain_message(
    name: str, message: str
) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json={"name": name})

    assert problem(response, 422, "invalid-value")["detail"] == message


async def test_the_vendor_name_limit_is_accepted() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await http.post(URL, json={"name": "a" * 100})

    assert vendor.status_code == 201, vendor.text


async def test_a_nul_in_the_name_is_422() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json={"name": "a\u0000b"})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("body", [{}, {"name": 1}, {"name": "SAP", "extra": 1}])
async def test_a_malformed_body_is_request_validation(body: dict[str, object]) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json=body)

    problem(response, 422, "request-validation")


# ---- 중복 (AC-3) ----


async def test_duplicate_vendor_name_ignoring_case_is_409() -> None:
    async with client_for(FakeUseCases()) as http:
        await make_vendor(http, "SAP")
        response = await http.post(URL, json={"name": "sap"})

    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 Vendor 이름입니다."


async def test_renaming_to_its_own_name_in_other_case_is_allowed() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http, "Sap")
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP"})

    assert response.status_code == 200, response.text


# ---- 삭제 (AC-4) ----


async def test_delete_vendor_is_204_and_removes_it() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        response = await http.delete(f"{URL}/{vendor['id']}")
        listed = await http.get(URL)

    assert response.status_code == 204
    assert listed.json() == []


async def test_delete_missing_vendor_is_404() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.delete(f"{URL}/{MISSING_ID}")

    problem(response, 404, "not-found")


async def test_a_malformed_vendor_id_is_request_validation() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.delete(f"{URL}/not-an-id")

    problem(response, 422, "request-validation")
