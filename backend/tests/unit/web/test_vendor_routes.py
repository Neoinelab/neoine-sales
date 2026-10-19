"""Vendor·Solution 라우터(AC-1~7): FakeUseCases 위의 HTTP 계약, 문구, 권한(401·403).

DB 없이 라우터·스키마·오류 매핑·권한을 빠르게 확인하는 단위 테스트다. 실제 DB를 지나는 시나리오는
functional(admin/test_vendors.py)이 맡는다.
"""

from uuid import uuid4

import pytest

from app.domain.auth.principal import Role
from tests.fakes.use_cases import FakeUseCases
from tests.unit.web.vendor_http import (
    SOLUTION_KEYS,
    URL,
    VENDOR_KEYS,
    client_for,
    make_solution,
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
    assert (body["name"], body["usage_count"], body["solutions"]) == ("SAP", 0, [])
    assert response.headers["location"] == f"{URL}/{body['id']}"


async def test_list_orders_vendors_and_solutions_by_lower_name() -> None:
    async with client_for(FakeUseCases()) as http:
        zeta = await make_vendor(http, "zeta")
        sap = await make_vendor(http, "SAP")
        await make_solution(http, sap["id"], "beta")
        await make_solution(http, sap["id"], "Alpha")
        body = (await http.get(URL)).json()

    assert [v["name"] for v in body] == ["SAP", "zeta"]
    assert [s["name"] for s in body[0]["solutions"]] == ["Alpha", "beta"]
    assert set(body[0]["solutions"][0]) == SOLUTION_KEYS
    assert body[0]["solutions"][0]["vendor_id"] == sap["id"]
    assert zeta["id"] == body[1]["id"]


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_may_list_vendors(role: Role) -> None:
    async with client_for(FakeUseCases(), role=role) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    assert response.json() == []


# ---- 이름 변경 (AC-2) ----


async def test_rename_vendor_returns_the_renamed_vendor() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP Korea"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "SAP Korea"
    assert set(response.json()) == VENDOR_KEYS


# ---- Solution (AC-3) ----


async def test_create_rename_and_delete_a_solution() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        created = await http.post(f"{URL}/{vendor['id']}/solutions", json={"name": " S/4 "})
        solution = created.json()
        renamed = await http.patch(
            f"{URL}/{vendor['id']}/solutions/{solution['id']}", json={"name": "S/4HANA"}
        )
        deleted = await http.delete(f"{URL}/{vendor['id']}/solutions/{solution['id']}")
        listed = (await http.get(URL)).json()

    assert created.status_code == 201, created.text
    assert created.headers["location"] == f"{URL}/{vendor['id']}/solutions/{solution['id']}"
    assert set(solution) == SOLUTION_KEYS
    assert (solution["name"], solution["usage_count"], solution["vendor_id"]) == (
        "S/4",
        0,
        vendor["id"],
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "S/4HANA"
    assert deleted.status_code == 204
    assert listed[0]["solutions"] == []


async def test_a_solution_id_of_another_vendor_is_404() -> None:
    async with client_for(FakeUseCases()) as http:
        sap = await make_vendor(http, "SAP")
        oracle = await make_vendor(http, "Oracle")
        solution = await make_solution(http, sap["id"], "Cloud")
        renamed = await http.patch(
            f"{URL}/{oracle['id']}/solutions/{solution['id']}", json={"name": "X"}
        )
        deleted = await http.delete(f"{URL}/{oracle['id']}/solutions/{solution['id']}")

    problem(renamed, 404, "not-found")
    problem(deleted, 404, "not-found")


async def test_solution_of_a_missing_vendor_is_404() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(f"{URL}/{uuid4()}/solutions", json={"name": "Cloud"})

    problem(response, 404, "not-found")


# ---- 이름 규칙 (AC-4) ----


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


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("   ", "Solution 이름을 입력하세요."),
        ("a" * 201, "Solution 이름은 200자 이내로 입력하세요."),
    ],
)
async def test_invalid_solution_names_are_422_with_the_domain_message(
    name: str, message: str
) -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        response = await http.post(f"{URL}/{vendor['id']}/solutions", json={"name": name})

    assert problem(response, 422, "invalid-value")["detail"] == message


async def test_the_limits_are_accepted() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await http.post(URL, json={"name": "a" * 100})
        solution = await http.post(
            f"{URL}/{vendor.json()['id']}/solutions", json={"name": "a" * 200}
        )

    assert (vendor.status_code, solution.status_code) == (201, 201)


async def test_a_nul_in_the_name_is_422() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json={"name": "a\u0000b"})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("body", [{}, {"name": 1}, {"name": "SAP", "extra": 1}])
async def test_a_malformed_body_is_request_validation(body: dict[str, object]) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.post(URL, json=body)

    problem(response, 422, "request-validation")


# ---- 중복 (AC-5) ----


async def test_duplicate_vendor_name_ignoring_case_is_409() -> None:
    async with client_for(FakeUseCases()) as http:
        await make_vendor(http, "SAP")
        response = await http.post(URL, json={"name": "sap"})

    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 Vendor 이름입니다."


async def test_duplicate_solution_is_409_but_another_vendor_may_reuse_the_name() -> None:
    async with client_for(FakeUseCases()) as http:
        sap = await make_vendor(http, "SAP")
        oracle = await make_vendor(http, "Oracle")
        await make_solution(http, sap["id"], "Cloud")
        duplicate = await http.post(f"{URL}/{sap['id']}/solutions", json={"name": "cloud"})
        other = await http.post(f"{URL}/{oracle['id']}/solutions", json={"name": "Cloud"})

    assert problem(duplicate, 409, "already-exists")["detail"] == (
        "이 Vendor에 이미 있는 Solution 이름입니다."
    )
    assert other.status_code == 201, other.text


async def test_renaming_to_its_own_name_in_other_case_is_allowed() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http, "Sap")
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP"})

    assert response.status_code == 200, response.text


# ---- 삭제 (AC-6) ----


async def test_delete_vendor_is_204_and_removes_its_solutions() -> None:
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        await make_solution(http, vendor["id"], "Cloud")
        response = await http.delete(f"{URL}/{vendor['id']}")
        listed = await http.get(URL)

    assert response.status_code == 204
    assert listed.json() == []


async def test_delete_missing_vendor_is_404() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.delete(f"{URL}/{uuid4()}")

    problem(response, 404, "not-found")


async def test_a_malformed_vendor_id_is_request_validation() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.delete(f"{URL}/not-a-uuid")

    problem(response, 422, "request-validation")
