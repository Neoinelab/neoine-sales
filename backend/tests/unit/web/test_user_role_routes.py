"""PUT /api/v1/users/{user_id}/role(R1 AC1-1~1-8): FakeUseCases 위의 HTTP 계약, 오류 매핑, 권한.

DB 없이 라우터·스키마·오류 매핑을 확인하는 단위 테스트다. 실제 DB를 지나는 시나리오는 functional
(users/test_user_role_change.py)이 맡는다.
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.functional.steps.users import USER_KEYS
from tests.support.ids import MISSING_ID
from tests.unit.web.vendor_http import SESSION_COOKIE, client_for, problem

USERS = "/api/v1/users"


def _url(user_id: object) -> str:
    return f"{USERS}/{user_id}/role"


async def test_admin_changes_the_role_and_gets_the_documented_user_body() -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        response = await http.put(_url(kim.id), json={"role": "user"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["id"], body["login_id"], body["role"]) == (kim.id, "kim", "user")
    assert type(body["id"]) is int


async def test_the_changed_role_is_visible_in_the_user_list() -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        await http.put(_url(kim.id), json={"role": "admin"})
        listed = (await http.get(USERS)).json()["items"]

    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "admin"


async def test_same_role_returns_the_user_unchanged() -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        before = next(u for u in (await http.get(USERS)).json()["items"] if u["login_id"] == "kim")
        response = await http.put(_url(kim.id), json={"role": "sales"})

    assert response.status_code == 200, response.text
    assert response.json() == before


async def test_the_targets_existing_session_sees_the_new_role_on_its_next_request() -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    kim_token = await use_cases.login_as(make_principal("kim", Role.SALES))
    async with client_for(use_cases) as http:
        before = await http.get("/api/v1/auth/me", cookies={SESSION_COOKIE: kim_token})
        await http.put(_url(kim.id), json={"role": "user"})
        after = await http.get("/api/v1/auth/me", cookies={SESSION_COOKIE: kim_token})

    assert before.status_code == after.status_code == 200
    assert (before.json()["role"], after.json()["role"]) == ("sales", "user")


async def test_changing_ones_own_role_is_a_409_with_the_documented_message() -> None:
    use_cases = FakeUseCases()
    async with client_for(use_cases) as http:
        me = (await http.get("/api/v1/auth/me")).json()
        response = await http.put(_url(me["user_id"]), json={"role": "user"})

    assert (
        problem(response, 409, "invalid-state")["detail"] == "자기 자신의 역할은 바꿀 수 없습니다."
    )


async def test_a_resigned_user_is_a_409() -> None:
    use_cases = FakeUseCases()
    gone = await use_cases.seed_user("gone", Role.SALES)
    await use_cases.resign_user(gone.id)
    async with client_for(use_cases) as http:
        response = await http.put(_url(gone.id), json={"role": "user"})

    assert problem(response, 409, "invalid-state")["detail"] == "이미 퇴사 처리된 사용자입니다"


@pytest.mark.parametrize("login_id", ["dev-admin", "dev-sales", "dev-user"])
async def test_dev_login_users_are_a_409(login_id: str) -> None:
    use_cases = FakeUseCases()
    dev = await use_cases.seed_user(login_id, Role.SALES)
    async with client_for(use_cases) as http:
        response = await http.put(_url(dev.id), json={"role": "user"})

    detail = problem(response, 409, "invalid-state")["detail"]
    assert detail == "개발 로그인 전용 사용자의 역할은 바꿀 수 없습니다."


async def test_an_unknown_user_is_a_404() -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.put(_url(MISSING_ID), json={"role": "user"})

    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", "0"])
async def test_a_malformed_user_id_is_a_422(bad_id: str) -> None:
    async with client_for(FakeUseCases()) as http:
        response = await http.put(_url(bad_id), json={"role": "user"})

    problem(response, 422, "request-validation")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"role": None},
        {"role": ""},
        {"role": "superuser"},
        {"role": "ADMIN"},
        {"role": 1},
        {"role": "user", "login_id": "x"},
    ],
)
async def test_an_invalid_body_is_a_422(body: dict[str, Any]) -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        response = await http.put(_url(kim.id), json=body)
        listed = (await http.get(USERS)).json()["items"]

    problem(response, 422, "request-validation")
    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "sales"


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_non_admins_get_403_and_nothing_changes(role: Role) -> None:
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases, role=role) as http:
        response = await http.put(_url(kim.id), json={"role": "admin"})

    problem(response, 403, "forbidden")
    async with client_for(use_cases) as admin_http:
        listed = (await admin_http.get(USERS)).json()["items"]
    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "sales"


async def test_forbidden_precedes_body_validation() -> None:
    async with client_for(FakeUseCases(), role=Role.SALES) as http:
        response = await http.put(_url(MISSING_ID), json={"unexpected": 1})

    problem(response, 403, "forbidden")


async def test_without_login_the_request_is_a_401() -> None:
    async with client_for(FakeUseCases(), role=None) as http:
        response = await http.put(_url(MISSING_ID), json={"role": "user"})

    problem(response, 401, "unauthenticated")


async def test_openapi_documents_the_route_and_the_role_request_schema() -> None:
    from app.main import create_app  # noqa: PLC0415
    from tests.functional.conftest import make_settings  # noqa: PLC0415
    from tests.unit.web.vendor_http import UNUSED_DATABASE_URL  # noqa: PLC0415

    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()

    operation = spec["paths"]["/api/v1/users/{user_id}/role"]["put"]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request = spec["components"]["schemas"][request_ref.rsplit("/", 1)[-1]]
    assert set(request["properties"]) == {"role"}
    assert request["required"] == ["role"]
    assert request.get("additionalProperties") is False
    assert {"200", "404", "409", "422"} <= set(operation["responses"])
