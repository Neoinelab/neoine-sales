"""Action 유형 라우터(AC-1~6): FakeUseCases 위의 HTTP 계약, 문구, 상태 코드.

DB 없이 라우터·스키마·오류 매핑을 빠르게 확인하는 단위 테스트다. 실제 DB를 지나는 시나리오는
functional(admin/test_action_types.py)이 맡는다. 권한은 test_action_type_route_permissions.py.
"""

from uuid import uuid4

import pytest

from app.domain.auth.principal import Role
from tests.unit.web.action_type_http import (
    DEFAULT_NAMES,
    TYPE_KEYS,
    URL,
    seeded_use_cases,
    type_id_of,
    use_type,
)
from tests.unit.web.vendor_http import client_for, problem

# ---- 조회 (AC-1) ----


async def test_list_returns_the_defaults_in_order_with_the_documented_keys() -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.get(URL)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["name"] for item in body] == DEFAULT_NAMES
    assert all(set(item) == TYPE_KEYS for item in body)
    assert all(item["is_default"] is True for item in body)
    assert all(item["created_by"] is None for item in body)
    assert all(item["usage_count"] == 0 for item in body)


async def test_custom_types_follow_the_defaults_in_lower_name_order() -> None:
    async with client_for(seeded_use_cases()) as http:
        for name in ("Zeta", "alpha", "나중"):
            assert (await http.post(URL, json={"name": name})).status_code == 201
        body = (await http.get(URL)).json()

    assert [item["name"] for item in body] == [*DEFAULT_NAMES, "alpha", "Zeta", "나중"]


async def test_list_reports_how_many_actions_use_each_type() -> None:
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=3)
    await use_type(use_cases, "데모", count=1)
    async with client_for(use_cases) as http:
        body = (await http.get(URL)).json()

    usage = {item["name"]: item["usage_count"] for item in body}
    assert (usage["미팅"], usage["데모"], usage["통화"]) == (3, 1, 0)


# ---- 생성 (AC-2·3·4) ----


@pytest.mark.parametrize("role", [Role.SALES, Role.ADMIN])
async def test_create_returns_201_with_location_and_the_creator(role: Role) -> None:
    async with client_for(seeded_use_cases(), role=role) as http:
        response = await http.post(URL, json={"name": "  웨비나  "})

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == TYPE_KEYS
    assert (body["name"], body["is_default"], body["usage_count"]) == ("웨비나", False, 0)
    assert body["created_by"] is not None
    assert response.headers["location"] == f"{URL}/{body['id']}"


async def test_the_created_type_is_listed_afterwards() -> None:
    async with client_for(seeded_use_cases()) as http:
        created = (await http.post(URL, json={"name": "웨비나"})).json()
        listed = (await http.get(URL)).json()

    assert created["id"] in [item["id"] for item in listed]


@pytest.mark.parametrize(
    ("name", "message"),
    [
        ("   ", "유형을 입력하세요."),
        ("", "유형을 입력하세요."),
        ("가" * 51, "유형은 50자 이내로 입력하세요."),
    ],
)
async def test_invalid_names_are_422_with_the_domain_message(name: str, message: str) -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.post(URL, json={"name": name})

    assert problem(response, 422, "invalid-value")["detail"] == message


async def test_a_50_character_name_is_accepted() -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.post(URL, json={"name": "가" * 50})

    assert response.status_code == 201, response.text


async def test_a_nul_in_the_name_is_422() -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.post(URL, json={"name": "웨\u0000비나"})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("body", [{}, {"name": 1}, {"name": "웨비나", "extra": 1}])
async def test_a_malformed_body_is_request_validation(body: dict[str, object]) -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.post(URL, json=body)

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("name", ["demo", "DEMO", " Demo "])
async def test_a_duplicate_name_ignoring_case_is_409(name: str) -> None:
    async with client_for(seeded_use_cases()) as http:
        assert (await http.post(URL, json={"name": "Demo"})).status_code == 201
        response = await http.post(URL, json={"name": name})

    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


async def test_the_name_of_a_seeded_default_is_taken() -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.post(URL, json={"name": "미팅"})

    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


# ---- 이름 변경 (AC-4·5) ----


async def test_rename_returns_the_renamed_default_type() -> None:
    async with client_for(seeded_use_cases()) as http:
        meeting = await type_id_of(http, "미팅")
        response = await http.patch(f"{URL}/{meeting}", json={"name": "  회의  "})
        listed = (await http.get(URL)).json()

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["name"], body["is_default"]) == (meeting, "회의", True)
    assert set(body) == TYPE_KEYS
    assert [item["name"] for item in listed][1] == "회의"  # 기본 순서(2번째)는 그대로


async def test_rename_reports_the_usage_count() -> None:
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=2)
    async with client_for(use_cases) as http:
        meeting = await type_id_of(http, "미팅")
        response = await http.patch(f"{URL}/{meeting}", json={"name": "회의"})

    assert response.json()["usage_count"] == 2


async def test_renaming_only_the_case_of_its_own_name_is_allowed() -> None:
    async with client_for(seeded_use_cases()) as http:
        created = (await http.post(URL, json={"name": "Webinar"})).json()
        response = await http.patch(f"{URL}/{created['id']}", json={"name": "WEBINAR"})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "WEBINAR"


async def test_rename_to_another_types_name_ignoring_case_is_409() -> None:
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        await http.post(URL, json={"name": "Webinar"})
        response = await http.patch(f"{URL}/{demo}", json={"name": "webinar"})

    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 유형 이름입니다."


async def test_rename_with_a_blank_name_is_422_and_with_an_unknown_id_is_404() -> None:
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        blank = await http.patch(f"{URL}/{demo}", json={"name": " "})
        missing = await http.patch(f"{URL}/{uuid4()}", json={"name": "무엇"})

    assert problem(blank, 422, "invalid-value")["detail"] == "유형을 입력하세요."
    problem(missing, 404, "not-found")


# ---- 삭제 (AC-6) ----


async def test_delete_an_unused_type_is_204_and_the_type_disappears() -> None:
    async with client_for(seeded_use_cases()) as http:
        demo = await type_id_of(http, "데모")
        response = await http.delete(f"{URL}/{demo}")
        listed = (await http.get(URL)).json()

    assert response.status_code == 204
    assert "데모" not in [item["name"] for item in listed]


async def test_delete_a_used_type_is_409_with_the_count_and_keeps_the_type() -> None:
    use_cases = seeded_use_cases()
    await use_type(use_cases, "미팅", count=2)
    async with client_for(use_cases) as http:
        meeting = await type_id_of(http, "미팅")
        response = await http.delete(f"{URL}/{meeting}")
        listed = (await http.get(URL)).json()

    detail = "사용 중인 유형은 삭제할 수 없습니다. (Action 2건)"
    assert problem(response, 409, "invalid-state")["detail"] == detail
    assert "미팅" in [item["name"] for item in listed]


async def test_delete_an_unknown_id_is_404() -> None:
    async with client_for(seeded_use_cases()) as http:
        response = await http.delete(f"{URL}/{uuid4()}")

    problem(response, 404, "not-found")


async def test_a_malformed_id_in_the_path_is_request_validation() -> None:
    async with client_for(seeded_use_cases()) as http:
        patched = await http.patch(f"{URL}/not-a-uuid", json={"name": "x"})
        deleted = await http.delete(f"{URL}/not-a-uuid")

    problem(patched, 422, "request-validation")
    problem(deleted, 422, "request-validation")
