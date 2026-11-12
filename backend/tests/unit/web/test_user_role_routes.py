"""PUT /api/v1/users/{user_id}/role: FakeUseCases 위의 HTTP 계약, 오류 매핑, 권한.

DB 없이 라우터·스키마·오류 매핑을 확인하는 단위 테스트다.
역할 변경 규칙은 `tests/unit/application/`의
Fake 단위 테스트가 본다.
"""

from typing import Any

import pytest

from app.domain.auth.principal import Role
from tests.factories_auth import make_principal
from tests.fakes.use_cases import FakeUseCases
from tests.support.app_settings import USER_KEYS
from tests.support.ids import MISSING_ID
from tests.unit.web.vendor_http import SESSION_COOKIE, client_for, problem

USERS = "/api/v1/users"


def _url(user_id: object) -> str:
    return f"{USERS}/{user_id}/role"


async def test_admin_changes_the_role_and_gets_the_documented_user_body() -> None:
    """admin이 역할을 바꾸면 200과 문서화된 사용자 본문이 돌아온다

    테스트 코드: US-031
    """
    # given: sales kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        # when: 역할을 user로 바꾼다
        response = await http.put(_url(kim.id), json={"role": "user"})

    # then: 200이고 본문 키가 문서와 같으며 역할이 user다
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == USER_KEYS
    assert (body["id"], body["login_id"], body["role"]) == (kim.id, "kim", "user")
    assert type(body["id"]) is int


async def test_the_changed_role_is_visible_in_the_user_list() -> None:
    """바뀐 역할이 사용자 목록에 보인다

    테스트 코드: US-031
    """
    # given: sales kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        # when: 역할을 admin으로 바꾼 뒤 목록을 읽는다
        await http.put(_url(kim.id), json={"role": "admin"})
        # then: 목록의 kim이 admin이다
        listed = (await http.get(USERS)).json()["items"]

    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "admin"


async def test_same_role_returns_the_user_unchanged() -> None:
    """지금과 같은 역할을 보내면 200이고 사용자가 그대로 돌아온다

    테스트 코드: US-037
    """
    # given: sales kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        before = next(u for u in (await http.get(USERS)).json()["items"] if u["login_id"] == "kim")
        # when: 같은 역할을 보낸다
        response = await http.put(_url(kim.id), json={"role": "sales"})

    # then: 200이고 본문이 이전 목록 값과 같다
    assert response.status_code == 200, response.text
    assert response.json() == before


async def test_the_targets_existing_session_sees_the_new_role_on_its_next_request() -> None:
    """대상의 기존 세션은 다음 요청부터 새 역할을 본다

    테스트 코드: US-032
    """
    # given: 로그인한 sales kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    kim_token = await use_cases.login_as(make_principal("kim", Role.SALES))
    async with client_for(use_cases) as http:
        before = await http.get("/api/v1/auth/me", cookies={SESSION_COOKIE: kim_token})
        # when: admin이 kim의 역할을 user로 바꾼다
        await http.put(_url(kim.id), json={"role": "user"})
        # then: 바꾸기 전 sales, 바꾼 뒤 같은 세션이 user로 200이다
        after = await http.get("/api/v1/auth/me", cookies={SESSION_COOKIE: kim_token})

    assert before.status_code == after.status_code == 200
    assert (before.json()["role"], after.json()["role"]) == ("sales", "user")


async def test_changing_ones_own_role_is_a_409_with_the_documented_message() -> None:
    """자기 자신의 역할 변경은 문서화된 문구의 409이다

    테스트 코드: US-034
    """
    # given: admin 로그인
    use_cases = FakeUseCases()
    async with client_for(use_cases) as http:
        me = (await http.get("/api/v1/auth/me")).json()
        # when: 자기 역할을 바꾼다
        response = await http.put(_url(me["user_id"]), json={"role": "user"})

    # then: 409 invalid-state와 자기 자신 문구다
    assert (
        problem(response, 409, "invalid-state")["detail"] == "자기 자신의 역할은 바꿀 수 없습니다."
    )


async def test_a_resigned_user_is_a_409() -> None:
    """퇴사자의 역할 변경은 409이다

    테스트 코드: US-036
    """
    # given: 퇴사한 사용자
    use_cases = FakeUseCases()
    gone = await use_cases.seed_user("gone", Role.SALES)
    await use_cases.resign_user(gone.id)
    async with client_for(use_cases) as http:
        # when: 역할을 바꾼다
        response = await http.put(_url(gone.id), json={"role": "user"})

    # then: 409 invalid-state와 퇴사 처리 문구다
    assert problem(response, 409, "invalid-state")["detail"] == "이미 퇴사 처리된 사용자입니다"


async def test_an_unknown_user_is_a_404() -> None:
    """없는 사용자의 역할 변경은 404이다

    테스트 코드: US-038
    """
    async with client_for(FakeUseCases()) as http:
        # when: 없는 id의 역할을 바꾼다
        response = await http.put(_url(MISSING_ID), json={"role": "user"})

    # then: 404 not-found다
    problem(response, 404, "not-found")


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1", "0"])
async def test_a_malformed_user_id_is_a_422(bad_id: str) -> None:
    """역할 변경의 id 형식이 틀리면 422이다"""
    async with client_for(FakeUseCases()) as http:
        # when: 잘못된 id로 바꾼다
        response = await http.put(_url(bad_id), json={"role": "user"})

    # then: 422 request-validation이다
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
    """role이 없거나 3값 밖이거나 모르는 필드가 있으면 422이고 역할은 그대로다

    테스트 코드: US-039
    """
    # given: sales kim
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases) as http:
        # when: 틀린 본문으로 바꾼다
        response = await http.put(_url(kim.id), json=body)
        # then: 422 request-validation이고 kim은 sales 그대로다
        listed = (await http.get(USERS)).json()["items"]

    problem(response, 422, "request-validation")
    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "sales"


@pytest.mark.parametrize("role", [Role.SALES, Role.USER])
async def test_non_admins_get_403_and_nothing_changes(role: Role) -> None:
    """admin이 아니면 역할 변경은 403이고 대상은 바뀌지 않는다

    테스트 코드: US-075
    """
    # given: sales 또는 user 로그인
    use_cases = FakeUseCases()
    kim = await use_cases.seed_user("kim", Role.SALES)
    async with client_for(use_cases, role=role) as http:
        # when: kim의 역할을 바꾼다
        response = await http.put(_url(kim.id), json={"role": "admin"})

    # then: 403 forbidden이고 kim은 sales 그대로다
    problem(response, 403, "forbidden")
    async with client_for(use_cases) as admin_http:
        listed = (await admin_http.get(USERS)).json()["items"]
    assert {u["login_id"]: u["role"] for u in listed}["kim"] == "sales"


async def test_forbidden_precedes_body_validation() -> None:
    """권한 검사가 본문 검증보다 먼저다"""
    # given: sales 로그인
    async with client_for(FakeUseCases(), role=Role.SALES) as http:
        # when: 틀린 본문으로 바꾼다
        response = await http.put(_url(MISSING_ID), json={"unexpected": 1})

    # then: 403 forbidden이다
    problem(response, 403, "forbidden")


async def test_without_login_the_request_is_a_401() -> None:
    """로그인하지 않은 역할 변경은 401이다"""
    # given: 로그인 없음
    async with client_for(FakeUseCases(), role=None) as http:
        # when: 역할을 바꾼다
        response = await http.put(_url(MISSING_ID), json={"role": "user"})

    # then: 401 unauthenticated다
    problem(response, 401, "unauthenticated")


async def test_openapi_documents_the_route_and_the_role_request_schema() -> None:
    """OpenAPI 문서에 역할 변경 경로와 요청 스키마가 기술되어 있다."""
    from app.main import create_app  # noqa: PLC0415
    from tests.support.app_settings import make_settings  # noqa: PLC0415
    from tests.unit.web.vendor_http import UNUSED_DATABASE_URL  # noqa: PLC0415

    # when: OpenAPI 문서를 만든다
    spec = create_app(
        settings=make_settings(UNUSED_DATABASE_URL), use_cases=FakeUseCases()
    ).openapi()

    # then: 요청은 role 하나만 필수로 받고 추가 필드를 금지하며 응답 코드가 문서화되어 있다
    operation = spec["paths"]["/api/v1/users/{user_id}/role"]["put"]
    request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    request = spec["components"]["schemas"][request_ref.rsplit("/", 1)[-1]]
    assert set(request["properties"]) == {"role"}
    assert request["required"] == ["role"]
    assert request.get("additionalProperties") is False
    assert {"200", "404", "409", "422"} <= set(operation["responses"])
