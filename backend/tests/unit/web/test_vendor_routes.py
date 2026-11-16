"""Vendor 라우터: FakeUseCases 위의 HTTP 계약, 문구, 권한(401·403).

DB 없이 라우터·스키마·오류 매핑·권한을 확인하는 단위 테스트다.
규칙 판정은 application 단위 테스트가 맡는다.
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

# ---- 생성·조회 ----


async def test_create_vendor_returns_201_with_location_and_the_documented_body() -> None:
    """Vendor를 만들면 201·Location이고 문서의 키만 담고 사용 수는 0이다.

    테스트 코드: CL-047
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: '  SAP  '를 만든다
        response = await http.post(URL, json={"name": "  SAP  "})

    # then: 201, Location, 정규화된 이름, 사용 0, solutions 필드 없음이다
    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == VENDOR_KEYS
    assert (body["name"], body["usage_count"]) == ("SAP", 0)
    assert "solutions" not in body
    assert response.headers["location"] == f"{URL}/{body['id']}"


async def test_vendor_ids_are_json_integers() -> None:
    """Vendor id는 JSON 정수다.

    테스트 코드: CL-047
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: Vendor를 만들고 목록을 읽는다
        vendor = await make_vendor(http, "SAP")
        listed = (await http.get(URL)).json()

    # then: id가 정수다
    assert type(vendor["id"]) is int
    assert type(listed[0]["id"]) is int


async def test_list_vendors_response_has_no_solutions_field() -> None:
    """Vendor 목록 항목은 문서의 키만 담고 solutions가 없다.

    테스트 코드: CL-045
    """
    # given: Vendor 하나가 있다
    async with client_for(FakeUseCases()) as http:
        # when: 목록을 읽는다
        await make_vendor(http, "SAP")
        body = (await http.get(URL)).json()

    # then: 키가 정확히 id, name, usage_count, created_at, updated_at이다
    assert set(body[0]) == {"id", "name", "usage_count", "created_at", "updated_at"}
    assert set(body[0]) == VENDOR_KEYS


async def test_list_orders_vendors_by_lower_name() -> None:
    """Vendor 목록은 소문자 이름순이다.

    테스트 코드: CL-045
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: zeta, SAP, Alpha를 만들고 목록을 읽는다
        zeta = await make_vendor(http, "zeta")
        await make_vendor(http, "SAP")
        await make_vendor(http, "Alpha")
        body = (await http.get(URL)).json()

    # then: Alpha, SAP, zeta 순이다
    assert [v["name"] for v in body] == ["Alpha", "SAP", "zeta"]
    assert zeta["id"] == body[2]["id"]


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SALES, Role.USER])
async def test_every_role_may_list_vendors(role: Role) -> None:
    """모든 역할이 Vendor 목록을 볼 수 있고 빈 시스템은 빈 배열이다.

    테스트 코드: CL-045
    """
    # given: Vendor가 없는 새 시스템
    async with client_for(FakeUseCases(), role=role) as http:
        # when: 해당 역할이 목록을 부른다
        response = await http.get(URL)

    # then: 200이고 빈 배열이다
    assert response.status_code == 200, response.text
    assert response.json() == []


# ---- 이름 변경 ----


async def test_rename_vendor_returns_the_renamed_vendor() -> None:
    """admin이 Vendor 이름을 바꾸면 200과 바뀐 Vendor가 온다.

    테스트 코드: CL-053
    """
    # given: 'SAP' Vendor가 있다
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        # when: 'SAP Korea'로 바꾼다
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP Korea"})

    # then: 200, 새 이름, 문서의 키다
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "SAP Korea"
    assert set(response.json()) == VENDOR_KEYS


# ---- Solution 관리 API는 폐지됐다 ----


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
    """예전 Solution 관리 경로는 404이고 Vendor는 그대로다.

    테스트 코드: CL-062
    """
    # given: 'SAP' Vendor가 있다
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        # when: Product 경로를 부른다
        response = await http.request(method, URL + path.format(vendor_id=vendor["id"]), json=body)
        listed = (await http.get(URL)).json()

    # then: 404이고 Vendor 목록은 'SAP' 그대로다
    assert response.status_code == 404, response.text
    assert [v["name"] for v in listed] == ["SAP"]


# ---- 이름 규칙 ----


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
    """공백뿐인 이름과 101자 이름은 Vendor 문구로 422다.

    테스트 코드: CL-050
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: 유효하지 않은 이름으로 만든다
        response = await http.post(URL, json={"name": name})

    # then: 422 invalid-value와 해당 문구다
    assert problem(response, 422, "invalid-value")["detail"] == message


async def test_the_vendor_name_limit_is_accepted() -> None:
    """Vendor 이름은 100자까지 만들어진다.

    테스트 코드: CL-050
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: 100자 이름으로 만든다
        vendor = await http.post(URL, json={"name": "a" * 100})

    # then: 201이다
    assert vendor.status_code == 201, vendor.text


async def test_a_nul_in_the_name_is_422() -> None:
    """NUL 문자가 든 Vendor 이름은 422이고 저장되지 않는다.

    테스트 코드: CL-051
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: NUL이 든 이름으로 만든다
        response = await http.post(URL, json={"name": "a\u0000b"})
        listed = (await http.get(URL)).json()

    # then: 422 NUL 문구이고 Vendor는 없다
    detail = problem(response, 422, "invalid-value")["detail"]
    assert detail == "Vendor 이름에는 NUL 문자를 쓸 수 없습니다"
    assert listed == []


@pytest.mark.parametrize("body", [{}, {"name": 1}, {"name": "SAP", "extra": 1}])
async def test_a_malformed_body_is_request_validation(body: dict[str, object]) -> None:
    """이름 누락·정수 이름·모르는 필드는 422 request-validation이다.

    테스트 코드: CL-052
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: 형식이 틀린 본문으로 만든다
        response = await http.post(URL, json=body)

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


# ---- 중복 ----


async def test_duplicate_vendor_name_ignoring_case_is_409() -> None:
    """대소문자만 다른 Vendor 이름은 409다.

    테스트 코드: CL-049
    """
    # given: 'SAP' Vendor가 있다
    async with client_for(FakeUseCases()) as http:
        await make_vendor(http, "SAP")
        # when: 'sap'을 만든다
        response = await http.post(URL, json={"name": "sap"})

    # then: 409 already-exists 문구다
    assert problem(response, 409, "already-exists")["detail"] == "이미 있는 Vendor 이름입니다."


async def test_renaming_to_its_own_name_in_other_case_is_allowed() -> None:
    """Vendor 자기 이름의 대소문자만 바꾸는 것은 허용된다.

    테스트 코드: CL-054
    """
    # given: 'Sap' Vendor가 있다
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http, "Sap")
        # when: 'SAP'로 바꾼다
        response = await http.patch(f"{URL}/{vendor['id']}", json={"name": "SAP"})

    # then: 200이다
    assert response.status_code == 200, response.text


# ---- 삭제 ----


async def test_delete_vendor_is_204_and_removes_it() -> None:
    """쓰이지 않는 Vendor는 삭제된다.

    테스트 코드: CL-059
    """
    # given: 'SAP' Vendor가 있다
    async with client_for(FakeUseCases()) as http:
        vendor = await make_vendor(http)
        # when: 삭제한다
        response = await http.delete(f"{URL}/{vendor['id']}")
        listed = await http.get(URL)

    # then: 204이고 목록이 비었다
    assert response.status_code == 204
    assert listed.json() == []


async def test_delete_missing_vendor_is_404() -> None:
    """없는 Vendor를 삭제하면 404다.

    테스트 코드: CL-057
    """
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: 없는 id를 삭제한다
        response = await http.delete(f"{URL}/{MISSING_ID}")

    # then: 404 not-found다
    problem(response, 404, "not-found")


async def test_a_malformed_vendor_id_is_request_validation() -> None:
    """경로의 Vendor id 형식이 틀리면 422 request-validation이다."""
    # given: admin으로 로그인
    async with client_for(FakeUseCases()) as http:
        # when: 정수가 아닌 id로 삭제를 부른다
        response = await http.delete(f"{URL}/not-an-id")

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")
